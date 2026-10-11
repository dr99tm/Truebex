// Everything the project screen shows, from the phone's replica first (so it
// opens offline) and then the network: the record, the digest, the followed
// set's newest manifest (long-polled on `rev`), the log (long-polled, every
// operation stored), presence as `client: "android"` (10 s while on screen,
// 30 s otherwise), prices, the outbox of edits and the history. The live loops
// back off per contract §8; the outbox goes out when the network returns.

import 'dart:async';
import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';

import '../actions/actions.dart';
import '../api/api.dart';
import '../config.dart';
import '../digest/digest.dart';
import '../outbox/outbox.dart';
import '../replica/database.dart';
import '../replica/replica.dart';
import '../services.dart';
import '../sync/backoff.dart';

enum ProjectStatus { loading, ready, missing, signedOut }

/// An edit the person asked for, before it becomes an operation.
class EditRequest {
  const EditRequest({required this.name, required this.label, required this.subject, required this.call});

  /// The undo-step name the desktop shows.
  final String name;

  /// What the app lists ("Floor finish: Oak boards").
  final String label;

  /// The entity it concerns, for its "Pending" badge.
  final String subject;
  final ToolCall call;
}

class ProjectController extends ChangeNotifier {
  ProjectController(this.services, this.pid, {Stream<List<ConnectivityResult>>? connectivity}) : _connectivity = connectivity; // ignore: prefer_initializing_formals

  final Services services;
  final String pid;
  final Stream<List<ConnectivityResult>>? _connectivity;

  ProjectStatus status = ProjectStatus.loading;
  bool offline = false;
  String error = '';
  Project? project;
  OpenProject? record;
  DigestSnapshot? digest;
  List<PanoramaSet> sets = [];
  SetState? set;
  int updatedFaces = 0;
  List<Presence> others = [];
  Map<String, Price> prices = {};
  List<OutboxEntry> entries = [];
  List<HistoryItem> history = [];
  Map<String, String> authorNames = {};
  Map<String, Object?>? me;

  /// Where the person looks (the panorama tells), for nudges and presence.
  double yawDeg = 0;
  double pitchDeg = 0;
  String? viewId;

  final String _session = hex32();
  bool _disposed = false;
  bool _foreground = true;
  final List<StreamSubscription<Object?>> _subs = [];
  final Completer<void> _stop = Completer<void>();
  Timer? _beat;
  DateTime _digestChecked = DateTime.fromMillisecondsSinceEpoch(0);

  Replica get _replica => services.replica;
  TruebexApi get _api => services.api;

  bool get canEdit => (record?.role.toJson() ?? project?.role) != 'viewer' && (record != null || project != null);
  String? get authorId => me?['author_id'] as String?;
  int get pendingCount => entries.where((e) => e.state == EntryState.pending).length;

  Set<String> get pendingSubjects => {
        for (final e in entries)
          if (e.state == EntryState.pending && e.subject != null) e.subject!,
      };

  void _changed() {
    if (!_disposed) notifyListeners();
  }

  Future<void> start() async {
    await _loadLocal();
    _subs.add(_replica.watchOutbox(pid).listen((rows) async {
      entries = rows;
      await _loadHistory();
      _changed();
    }));
    _subs.add((_connectivity ?? Connectivity().onConnectivityChanged).listen((kinds) {
      if (kinds.any((k) => k != ConnectivityResult.none)) {
        unawaited(sync());
      } else if (!offline) {
        offline = true;
        _changed();
      }
    }));
    await sync(first: true);
    if (_disposed || status != ProjectStatus.ready) return;
    unawaited(_followLog());
    unawaited(_followSet());
    _scheduleBeat(Duration.zero);
  }

  Future<void> _loadLocal() async {
    me = await _replica.json('me');
    project = await _replica.project(pid);
    if (project?.record != null) record = OpenProject.fromJson(jsonDecode(project!.record!));
    digest = await _replica.digest(pid);
    final setId = project?.setId;
    if (setId != null) set = await _replica.manifest(pid, setId);
    final cachedSets = await _replica.json('sets:$pid');
    sets = PanoramaSet.listFromJson(cachedSets?['sets']);
    prices = _pricesOf(await _replica.json('prices:$pid'));
    authorNames = await _replica.authorNames(pid);
    entries = (await _replica.list(pid)).reversed.toList();
    await _loadHistory();
    if (project != null) status = ProjectStatus.ready;
    _changed();
  }

  Map<String, Price> _pricesOf(Map<String, Object?>? json) => {
        for (final e in (json ?? const {}).entries)
          e.key: ?Price.fromJson(e.value),
      };

  Future<void> _loadHistory() async {
    history = await _replica.history(pid, me: authorId);
  }

  /// Push the outbox, pull, refresh the digest and the set (the engine's one sync).
  Future<void> sync({bool first = false}) async {
    final report = await services.engine.syncProject(pid);
    if (_disposed) return;
    if (report.signedOut) {
      status = ProjectStatus.signedOut;
    } else if (report.offline) {
      offline = true;
      if (project != null) status = ProjectStatus.ready;
    } else if (report.failure == null) {
      offline = false;
    }
    final known = await _replica.project(pid);
    if (known == null && !report.offline && !report.signedOut) {
      status = first ? ProjectStatus.missing : status;
    }
    await _loadLocal();
    if (report.prefetchWanted) unawaited(services.scheduler.prefetchWhenIdle());
    if (report.failure != null && !report.offline && !report.signedOut && report.failure!.status != 404) {
      error = report.failure!.message;
    }
    _changed();
  }

  /// The log (5.7): every new operation is stored on the phone as it lands.
  Future<void> _followLog() async {
    final backoff = Backoff();
    while (!_disposed) {
      try {
        final after = (await _replica.project(pid))?.pulledSeq ?? 0;
        final asked = DateTime.now();
        final page = await _api.pull(pid, after, waitS: 25, abort: _stop.future);
        if (_disposed) return;
        // A server that answers an empty long-poll at once is not asked again at once.
        if (page.ops.isEmpty) await _atLeast(asked, minPoll);
        backoff.reset();
        final wasOffline = offline;
        offline = false;
        await _replica.storePage(pid, page);
        if (page.ops.isNotEmpty) {
          project = await _replica.project(pid);
          await _loadHistory();
          if (DateTime.now().difference(_digestChecked) > const Duration(seconds: 30)) {
            _digestChecked = DateTime.now();
            if (await services.engine.refreshDigest(pid)) digest = await _replica.digest(pid);
          }
        }
        if (wasOffline) unawaited(sync());
        _changed();
      } on ApiFailure catch (e) {
        if (_disposed) return;
        if (e.unauthenticated) {
          if (await services.auth.renewSilently()) continue;
          status = ProjectStatus.signedOut;
          _changed();
          return;
        }
        if (e.offline && !offline) {
          offline = true;
          _changed();
        }
        if (!e.retryable) return;
        await _sleep(backoff.next(retryAfter: e.retryAfter));
      } catch (_) {
        if (_disposed) return;
        await _sleep(backoff.next());
      }
    }
  }

  /// The followed set: long-poll its `rev` and take each newer manifest.
  Future<void> _followSet() async {
    final backoff = Backoff();
    SetState? prev = set;
    while (!_disposed) {
      final setId = (await _replica.project(pid))?.setId;
      if (setId == null) {
        await _sleep(const Duration(seconds: 60));
        if (!_disposed) await services.engine.refreshManifest(pid).catchError((_) => false);
        continue;
      }
      try {
        final asked = DateTime.now();
        final state = await _api.setState(pid, setId, rev: prev?.rev ?? -1, waitS: 25, abort: _stop.future);
        if (_disposed) return;
        backoff.reset();
        if (prev != null && state.rev <= prev.rev) await _atLeast(asked, minPoll);
        if (prev == null || state.rev > prev.rev) {
          updatedFaces = prev == null ? 0 : changedFaces(prev, state);
          prev = state;
          set = state;
          await _replica.putManifest(pid, setId, state);
          if (project?.starred ?? false) unawaited(services.scheduler.prefetchWhenIdle());
          _changed();
        }
      } on ApiFailure catch (e) {
        if (_disposed) return;
        if (e.status == 404) {
          await services.engine.refreshManifest(pid).catchError((_) => false);
          prev = null;
        }
        await _sleep(backoff.next(retryAfter: e.retryAfter));
      } catch (_) {
        if (_disposed) return;
        await _sleep(backoff.next());
      }
    }
  }

  /// Presence (5.17) as `client: "android"` with the view the person looks at.
  void _scheduleBeat(Duration after) {
    _beat?.cancel();
    if (_disposed) return;
    _beat = Timer(after, () async {
      await _heartbeat();
      _scheduleBeat(Duration(seconds: _foreground ? 10 : 30));
    });
  }

  /// The body of 5.17: `client: "android"`, the view's storey, eye and bearing.
  PresenceIn presenceBody({bool leaving = false}) {
    final view = digest?.digest.view(currentViewId);
    return PresenceIn(
      replicaId: _replicaId ?? hex32(),
      client: 'android',
      view: view == null
          ? null
          : ViewIn(storey: view.storey, eyeMm: [for (final v in view.eyeMm ?? const <num>[]) v.toDouble()], yawDeg: yawDeg.roundToDouble()),
      selection: const [],
      editing: const [],
      leaving: leaving,
    );
  }

  String? _replicaId;

  Future<void> _heartbeat() async {
    _replicaId ??= await services.session.replicaId(pid);
    try {
      final answer = await _api.heartbeat(pid, presenceBody());
      others = answer.others;
      _changed();
    } on ApiFailure {
      // The log loop reports being offline.
    }
  }

  void setForeground(bool value) {
    _foreground = value;
    if (value) _scheduleBeat(Duration.zero);
  }

  void look(double yaw, double pitch) {
    yawDeg = yaw;
    pitchDeg = pitch;
  }

  /// The view on screen: the one chosen, else the set's first.
  String? get currentViewId => viewId ?? set?.manifest?.views.firstOrNull?.view;

  void chooseView(String id) {
    viewId = id;
    _changed();
  }

  /// Make an edit: an `action` operation in the outbox, sent now or when the network returns.
  Future<void> edit(EditRequest req) async {
    final author = authorId;
    if (author == null || !canEdit) {
      error = services.strings.sessionEnded;
      _changed();
      return;
    }
    final replicaId = _replicaId ??= await services.session.replicaId(pid);
    final base = (await _replica.project(pid))?.pulledSeq ?? 0;
    final op = buildActionOp(author: author, replicaId: replicaId, baseSeq: base, session: _session, name: req.name, call: req.call);
    await services.outbox.add(pid, op.toJson(), label: req.label, subject: req.subject);
    entries = (await _replica.list(pid)).reversed.toList();
    await _loadHistory();
    _changed();
    // Sent by the background job when the network returns, should the app close first.
    unawaited(services.scheduler.syncWhenOnline());
    if (!offline) {
      final out = await services.engine.flush(pid);
      // The push found no network: the edit waits, and says so.
      if (out.error?.offline ?? false) offline = true;
      project = await _replica.project(pid);
      entries = (await _replica.list(pid)).reversed.toList();
      await _loadHistory();
      _changed();
    }
  }

  Future<void> dismiss(String opId) => services.outbox.dismiss(opId);

  Future<void> toggleStar() async {
    final now = !(project?.starred ?? false);
    await _replica.setStarred(pid, now);
    project = await _replica.project(pid);
    if (now) unawaited(services.scheduler.prefetchWhenIdle());
    _changed();
  }

  Future<void> chooseSet(String setId) async {
    await _replica.setChosenSet(pid, setId);
    await services.engine.refreshManifest(pid).catchError((_) => false);
    await _loadLocal();
  }

  Future<void> _sleep(Duration d) => Future.any([Future<void>.delayed(d), _stop.future]);

  /// The shortest time between two long-polls that came back empty.
  static const minPoll = Duration(seconds: 2);

  Future<void> _atLeast(DateTime since, Duration gap) async {
    final left = gap - DateTime.now().difference(since);
    if (left > Duration.zero) await _sleep(left);
  }

  @override
  void dispose() {
    _disposed = true;
    if (!_stop.isCompleted) _stop.complete();
    _beat?.cancel();
    for (final s in _subs) {
      s.cancel();
    }
    if (_replicaId != null) unawaited(_api.heartbeat(pid, presenceBody(leaving: true)).then((_) {}, onError: (_) {}));
    super.dispose();
  }
}

/// Faces of every view whose tiles a newer manifest changed.
int changedFaces(SetState before, SetState after) {
  final old = {for (final v in before.manifest?.views ?? const <TileView>[]) v.view: v};
  var n = 0;
  for (final v in after.manifest?.views ?? const <TileView>[]) {
    final prev = old[v.view];
    final faces = {'n': v.faces.n, 'e': v.faces.e, 's': v.faces.s, 'w': v.faces.w, 'u': v.faces.u, 'd': v.faces.d};
    final was = prev == null
        ? null
        : {'n': prev.faces.n, 'e': prev.faces.e, 's': prev.faces.s, 'w': prev.faces.w, 'u': prev.faces.u, 'd': prev.faces.d};
    for (final f in faces.keys) {
      if (was == null || jsonEncode(was[f]!.tiles) != jsonEncode(faces[f]!.tiles)) n++;
    }
  }
  return n;
}

/// The tiles `truebex-tiles` MAJOR this release reads; a newer one says "Update needed".
bool manifestReadable(TileManifest m) {
  final major = int.tryParse(m.schema.split('/').last.split('.').first);
  return m.schema.startsWith('truebex-tiles/') && major == Config.tilesMajor;
}
