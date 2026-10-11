// One sync of the phone's replica (PF10 Scope 5), run by the background jobs
// and by the app when it opens a project or the network returns:
//
//   1. the project's record (members' author ids name who won a conflict)
//   2. push the outbox, ≤ 200 a request (§6.3 per operation; a rejection is
//      shown as a notification and in the history, never sent again)
//   3. pull every operation after the phone's newest, pages of ≤ 1000
//   4. refresh the snapshot's digest (and the products' prices with it)
//   5. refresh the followed sets' manifests; starred projects' tiles are
//      prefetched on unmetered networks
//
// A 401 renews a Google session silently once (the 24 h session lapsed);
// network errors leave everything for the next run (WorkManager retries with
// backoff; the app retries per contract §8).

import 'dart:convert';

import 'package:crypto/crypto.dart';

import '../api/api.dart';
import '../auth/session.dart';
import '../digest/digest.dart';
import '../outbox/outbox.dart';
import '../replica/replica.dart';
import '../viewer/tile_cache.dart';

/// Shows a rejection (§6.3 rule 4) where the person sees it.
abstract class Notifier {
  Future<void> rejected({required String projectName, required String projectId, required String text, required int id});
}

class SilentNotifier implements Notifier {
  final List<String> shown = [];

  @override
  Future<void> rejected({required String projectName, required String projectId, required String text, required int id}) async =>
      shown.add(text);
}

/// The texts a notification needs (from the app's strings; no BuildContext in the background).
class ConflictText {
  const ConflictText({required this.named, required this.self, required this.someone});
  final String Function(String name) named;
  final String self;
  final String someone;
}

class SyncReport {
  bool offline = false;
  bool signedOut = false;
  ApiFailure? failure;
  int pushed = 0;
  int pulled = 0;
  int rejected = 0;
  int tilesFetched = 0;

  /// A starred project's panorama moved: its tiles are worth fetching (unmetered, charging).
  bool prefetchWanted = false;

  /// Something to try again later (offline, the server busy).
  bool get retry => offline || (failure?.retryable ?? false);
}

/// The tile level this phone's viewer shows (the smallest at least `needPx` wide).
int levelFor(List<int> levels, int needPx) {
  final i = levels.indexWhere((px) => px >= needPx);
  return i == -1 ? levels.length - 1 : i;
}

/// The tiles of every view of a manifest at the level the phone shows.
Iterable<String> manifestTiles(TileManifest m, int needPx) sync* {
  for (final v in m.views) {
    final l = levelFor(v.levels, needPx);
    for (final face in [v.faces.n, v.faces.e, v.faces.s, v.faces.w, v.faces.u, v.faces.d]) {
      if (l < face.tiles.length) yield* face.tiles[l];
    }
  }
}

class SyncEngine {
  SyncEngine({
    required this.api,
    required this.replica,
    required this.session,
    required this.outbox,
    required this.tiles,
    required this.text,
    Notifier? notifier,
    this.reauth,
    this.needPx = 2048,
    DateTime Function()? clock,
  })  : notifier = notifier ?? SilentNotifier(),
        _clock = clock ?? DateTime.now;

  final TruebexApi api;
  final Replica replica;
  final Session session;
  final Outbox outbox;
  final TileCache tiles;
  final ConflictText text;
  final Notifier notifier;

  /// Renews the session without the person (a Google account); true when it did.
  final Future<bool> Function()? reauth;

  /// The tile level the viewer uses on this phone (pixels across a face).
  int needPx;
  final DateTime Function() _clock;

  Future<T> _authed<T>(Future<T> Function() call) async {
    try {
      return await call();
    } on ApiFailure catch (e) {
      if (!e.unauthenticated) rethrow;
      if (reauth != null && await reauth!()) return call();
      await session.expire();
      rethrow;
    }
  }

  /// The account (its author_id goes into every operation); kept for offline use.
  Future<Map<String, Object?>?> me() async {
    try {
      final me = await _authed(api.me);
      final json = {'id': me.id, 'email': me.email, 'name': me.name, 'author_id': me.authorId};
      await replica.putJson('me', json);
      return json;
    } on ApiFailure catch (e) {
      if (e.offline || e.retryable) return replica.json('me');
      rethrow;
    }
  }

  /// The background job: every project with edits waiting, starred, or opened before.
  Future<SyncReport> syncAll({bool unmetered = false, bool prefetch = false}) async {
    final report = SyncReport();
    if (!session.signedIn && !(reauth != null && await reauth!())) {
      report.signedOut = true;
      return report;
    }
    try {
      await me();
      final records = <ProjectRecord>[];
      String? cursor;
      do {
        final page = await _authed(() => api.listProjects(cursor: cursor));
        records.addAll(page.projects);
        cursor = page.nextCursor;
      } while (cursor != null);
      await replica.putProjectList(records);
      final pending = await replica.pendingCounts();
      for (final p in await replica.projects()) {
        if (!pending.containsKey(p.projectId) && !p.starred && p.record == null) continue;
        await syncProject(p.projectId, report: report, prefetchTiles: p.starred && (unmetered || prefetch));
        if (report.offline || report.signedOut) break;
      }
    } on ApiFailure catch (e) {
      _note(report, e);
    }
    return report;
  }

  void _note(SyncReport report, ApiFailure e) {
    report.failure = e;
    if (e.offline) report.offline = true;
    if (e.unauthenticated) report.signedOut = true;
  }

  /// Push this project's outbox now; rejections are notified.
  Future<FlushOutcome> flush(String pid, {SyncReport? report}) async {
    final out = await outbox.flush(pid, (replicaId, ops) => _authed(() => api.push(pid, replicaId, ops)));
    if (report != null) {
      report.pushed += out.accepted.length;
      report.rejected += out.rejected.length;
      if (out.error != null) _note(report, out.error!);
    }
    await notifyRejections(pid);
    return out;
  }

  /// Every rejection not yet shown, as "Sam changed this first — your edit was replaced".
  Future<void> notifyRejections(String pid) async {
    final found = await outbox.takeUnnotified(pid);
    if (found.isEmpty) return;
    final names = await replica.authorNames(pid);
    final mine = (await replica.json('me'))?['author_id'] as String?;
    final projectName = (await replica.project(pid))?.name ?? '';
    for (final e in found) {
      await notifier.rejected(projectName: projectName, projectId: pid, text: '${e.label}: ${conflictLine(e, names, mine)}', id: e.createdAt & 0x7fffffff);
    }
  }

  String conflictLine(OutboxEntry e, Map<String, String> names, String? me) {
    final winner = e.winning.isEmpty ? null : e.winning.first;
    if (winner != null && me != null && winner.author == me) return text.self;
    final name = winner == null ? null : names[winner.author];
    return text.named(name ?? text.someone);
  }

  Future<SyncReport> syncProject(String pid, {SyncReport? report, bool prefetchTiles = false}) async {
    final r = report ?? SyncReport();
    try {
      final record = await _authed(() => api.openProject(pid));
      await replica.putOpenProject(record);
      final out = await flush(pid, report: r);
      if (out.error != null && (out.error!.offline || out.error!.unauthenticated)) return r;
      final before = (await replica.project(pid))?.pulledSeq ?? 0;
      final top = await replica.pullAll(pid, (after) => _authed(() => api.pull(pid, after)));
      r.pulled += top - before;
      await refreshDigest(pid);
      final moved = await refreshManifest(pid);
      final starred = (await replica.project(pid))?.starred ?? false;
      if (moved && starred) r.prefetchWanted = true;
      if (prefetchTiles) r.tilesFetched += await prefetch(pid);
      await replica.markSynced(pid, _clock());
    } on ApiFailure catch (e) {
      if (e.status == 404) {
        // Unshared or deleted: nothing of it stays on the phone.
        await replica.forgetProject(pid);
      } else {
        _note(r, e);
      }
    }
    return r;
  }

  /// 5.9's digest file, fetched only when its hash changed; then the products' prices.
  Future<bool> refreshDigest(String pid) async {
    final snap = await _authed(() => api.latestSnapshot(pid));
    final file = snap?.files.digest;
    if (snap == null || file == null) return false;
    if (await replica.digestSha(pid) == file.sha256) {
      await replica.touchDigest(pid, snap);
      return false;
    }
    final bytes = await api.fetchBytes(Uri.parse(file.url));
    if (sha256.convert(bytes).toString() != file.sha256) return false;
    final body = utf8.decode(bytes);
    final digest = ProjectDigest.parse(jsonDecode(body));
    if (digest == null) return false;
    await replica.putDigest(pid, snap, file.sha256, body);
    await refreshPrices(pid, digest);
    return true;
  }

  /// Prices of the placed products for the project's region (PF7 5.5); optional.
  Future<void> refreshPrices(String pid, ProjectDigest digest) async {
    final region = digest.region;
    if (region == null || digest.products.isEmpty) return;
    try {
      final answer = await api.prices(region, [for (final p in digest.products) p.product]);
      await replica.putJson('prices:$pid', {
        for (final i in answer.items)
          if (i.price != null) '${i.supplierId}|${i.sku}|${i.variantId}': i.price!.toJson(),
      });
    } on ApiFailure {
      // The marketplace is optional: names show without prices.
    }
  }

  /// The followed set the phone shows: the one chosen before while it is listed, else the newest.
  Future<bool> refreshManifest(String pid) async {
    final sets = (await _authed(() => api.listSets(pid))).sets;
    await replica.putJson('sets:$pid', {'sets': [for (final s in sets) s.toJson()]});
    final chosen = (await replica.project(pid))?.setId;
    final keep = sets.where((s) => s.setId == chosen).firstOrNull ?? sets.firstOrNull;
    await replica.setChosenSet(pid, keep?.setId);
    if (keep == null) return false;
    final known = await replica.manifestRev(pid, keep.setId);
    if (known != null && known >= keep.rev) return false;
    final state = await _authed(() => api.setState(pid, keep.setId));
    await replica.putManifest(pid, keep.setId, state);
    return true;
  }

  /// Tiles of the chosen set's newest manifest at this phone's level; returns how many were added.
  Future<int> prefetch(String pid) async {
    final setId = (await replica.project(pid))?.setId;
    final state = setId == null ? null : await replica.manifest(pid, setId);
    final m = state?.manifest;
    if (m == null) return 0;
    final base = m.tilesBase.replaceAll(RegExp(r'/$'), '');
    var added = 0;
    for (final sha in manifestTiles(m, needPx).toSet()) {
      if (await tiles.has(sha)) continue;
      try {
        if (await tiles.put(sha, await api.fetchBytes(Uri.parse('$base/$sha.jpg')))) added++;
      } on ApiFailure catch (e) {
        if (e.offline) break;
      }
    }
    return added;
  }
}
