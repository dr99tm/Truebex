// The phone's replica of each project (PF10 Scope 2): the pulled log, kept
// whole and in server order, with `head_seq` and the highest stored number;
// the outbox; the newest digest and manifests. A light client never applies a
// delta: what the phone shows comes from the newest digest and the tiles,
// labelled with their operation and time, and the history reads the log.

import 'dart:convert';

import 'package:drift/drift.dart';

import '../api/api.dart';
import '../digest/digest.dart';
import '../outbox/outbox.dart';
import 'database.dart';

/// One line of the history: an operation from the log, or one of the phone's own edits.
class HistoryItem {
  HistoryItem({
    required this.name,
    required this.author,
    required this.at,
    this.serverSeq,
    this.kind = 'delta',
    this.mine = false,
    this.entry,
  });

  final String name;
  final String author;
  final String at;
  final int? serverSeq;
  final String kind;

  /// Written by this person (any of their devices).
  final bool mine;

  /// The phone's own edit, while pending, rejected or failed.
  final OutboxEntry? entry;
}

class Replica implements OutboxStore {
  Replica(this.db);

  final ReplicaDb db;

  // --- projects ------------------------------------------------------------------------------

  Future<List<Project>> projects() => (db.select(db.projects)..orderBy([(t) => OrderingTerm.desc(t.updatedAt)])).get();

  Future<Project?> project(String pid) => (db.select(db.projects)..where((t) => t.projectId.equals(pid))).getSingleOrNull();

  /// The list of 5.2 (complete): new and changed records in, unshared ones out with their data.
  Future<void> putProjectList(List<ProjectRecord> records) => db.transaction(() async {
        final keep = <String>{};
        for (final r in records) {
          keep.add(r.projectId);
          final known = await project(r.projectId);
          await db.into(db.projects).insertOnConflictUpdate(ProjectsCompanion(
                projectId: Value(r.projectId),
                name: Value(r.name),
                role: Value(r.role.toJson()),
                ownerName: Value(r.owner?.name),
                headSeq: Value(known == null ? r.headSeq : (r.headSeq > known.headSeq ? r.headSeq : known.headSeq)),
                updatedAt: Value(r.updatedAt),
              ));
        }
        for (final p in await projects()) {
          if (!keep.contains(p.projectId)) await forgetProject(p.projectId);
        }
      });

  /// The record of 5.3 (members with author ids, the quota) kept for offline use.
  Future<void> putOpenProject(OpenProject r) async {
    final known = await project(r.projectId);
    await db.into(db.projects).insertOnConflictUpdate(ProjectsCompanion(
          projectId: Value(r.projectId),
          name: Value(r.name),
          role: Value(r.role.toJson()),
          ownerName: Value(r.owner?.name),
          headSeq: Value(known == null || r.headSeq > known.headSeq ? r.headSeq : known.headSeq),
          record: Value(jsonEncode(r.toJson())),
          updatedAt: Value(r.updatedAt),
        ));
  }

  Future<void> forgetProject(String pid) => db.transaction(() async {
        await (db.delete(db.ops)..where((t) => t.projectId.equals(pid))).go();
        await (db.delete(db.outboxEntries)..where((t) => t.projectId.equals(pid))).go();
        await (db.delete(db.digests)..where((t) => t.projectId.equals(pid))).go();
        await (db.delete(db.manifests)..where((t) => t.projectId.equals(pid))).go();
        await (db.delete(db.projects)..where((t) => t.projectId.equals(pid))).go();
      });

  Future<void> setStarred(String pid, bool starred) =>
      (db.update(db.projects)..where((t) => t.projectId.equals(pid))).write(ProjectsCompanion(starred: Value(starred)));

  Future<void> markSynced(String pid, DateTime at) =>
      (db.update(db.projects)..where((t) => t.projectId.equals(pid))).write(ProjectsCompanion(syncedAt: Value(at)));

  Future<void> setChosenSet(String pid, String? setId) =>
      (db.update(db.projects)..where((t) => t.projectId.equals(pid))).write(ProjectsCompanion(setId: Value(setId)));

  /// Members of the stored 5.3 record: author id → name, to name who won a conflict.
  Future<Map<String, String>> authorNames(String pid) async {
    final p = await project(pid);
    if (p?.record == null) return {};
    final record = OpenProject.fromJson(jsonDecode(p!.record!));
    return {
      for (final m in record?.members ?? const <Member>[])
        if (m.authorId != null) m.authorId!: (m.name?.isNotEmpty ?? false) ? m.name! : m.email,
    };
  }

  // --- the log -------------------------------------------------------------------------------

  /// Store one pulled page (5.7) in order; `head_seq` moves to the page's.
  Future<int> storePage(String pid, PullPage page) => db.transaction(() async {
        var top = (await project(pid))?.pulledSeq ?? 0;
        for (final o in page.ops) {
          await db.into(db.ops).insert(
                OpsCompanion.insert(
                  projectId: pid,
                  serverSeq: o.serverSeq,
                  opId: o.opId,
                  replicaId: o.replicaId,
                  author: o.author,
                  authorKind: o.authorKind.toJson(),
                  kind: o.kind.toJson(),
                  name: o.name,
                  at: o.at,
                  baseSeq: o.baseSeq,
                  touched: jsonEncode(o.touched),
                  deltaFormat: Value(o.deltaFormat),
                  // Opaque: the base64 text as it arrived, never decoded here.
                  delta: Value(o.delta == null ? null : Uint8List.fromList(utf8.encode(o.delta!))),
                  action: Value(o.action == null ? null : jsonEncode(o.action!.toJson())),
                  restore: Value(o.restore == null ? null : jsonEncode(o.restore)),
                ),
                mode: InsertMode.insertOrIgnore,
              );
          if (o.serverSeq > top) top = o.serverSeq;
        }
        final known = await project(pid);
        final head = known == null || page.headSeq > known.headSeq ? page.headSeq : known.headSeq;
        await (db.update(db.projects)..where((t) => t.projectId.equals(pid)))
            .write(ProjectsCompanion(pulledSeq: Value(top), headSeq: Value(head)));
        return top;
      });

  /// Pull every page after what the phone holds (≤ 1000 a page) until the head.
  Future<int> pullAll(String pid, Future<PullPage> Function(int after) fetch, {int maxPages = 1000}) async {
    var after = (await project(pid))?.pulledSeq ?? 0;
    for (var i = 0; i < maxPages; i++) {
      final page = await fetch(after);
      after = await storePage(pid, page);
      if (!page.more || page.ops.isEmpty) break;
    }
    return after;
  }

  Future<int> opCount(String pid) async {
    final count = db.ops.serverSeq.count();
    final row = await (db.selectOnly(db.ops)..addColumns([count])..where(db.ops.projectId.equals(pid))).getSingle();
    return row.read(count) ?? 0;
  }

  /// The log, newest first, with the phone's own edits that are not in it.
  Future<List<HistoryItem>> history(String pid, {required String? me, int limit = 200}) async {
    final rows = await (db.select(db.ops)
          ..where((t) => t.projectId.equals(pid))
          ..orderBy([(t) => OrderingTerm.desc(t.serverSeq)])
          ..limit(limit))
        .get();
    final mine = await list(pid);
    final inLog = {for (final r in rows) r.opId};
    final items = <HistoryItem>[
      for (final e in mine)
        if (!inLog.contains(e.opId) && e.state != EntryState.dismissed && e.state != EntryState.accepted)
          HistoryItem(name: e.label, author: me ?? '', at: e.op['at'] as String, mine: true, kind: 'action', entry: e),
      for (final r in rows)
        HistoryItem(
          name: r.name,
          author: r.author,
          at: r.at,
          serverSeq: r.serverSeq,
          kind: r.kind,
          mine: r.author == me,
        ),
    ];
    return items;
  }

  // --- the outbox (OutboxStore) ----------------------------------------------------------------

  OutboxEntry _entry(OutboxEntryRow r) => OutboxEntry(
        opId: r.opId,
        projectId: r.projectId,
        op: (jsonDecode(r.op) as Map).cast<String, Object?>(),
        state: EntryState.values.byName(r.state),
        label: r.label,
        subject: r.subject,
        createdAt: r.createdAt,
        serverSeq: r.serverSeq,
        winning: [
          for (final w in (r.winning == null ? const [] : jsonDecode(r.winning!) as List))
            Winner.fromJson((w as Map).cast<String, Object?>()),
        ],
        reason: r.reason,
        notified: r.notified,
      );

  @override
  Future<List<OutboxEntry>> list(String projectId) async => [
        for (final r in await (db.select(db.outboxEntries)
              ..where((t) => t.projectId.equals(projectId))
              ..orderBy([(t) => OrderingTerm.asc(t.createdAt), (t) => OrderingTerm.asc(t.opId)]))
            .get())
          _entry(r),
      ];

  @override
  Future<OutboxEntry?> get(String opId) async {
    final r = await (db.select(db.outboxEntries)..where((t) => t.opId.equals(opId))).getSingleOrNull();
    return r == null ? null : _entry(r);
  }

  @override
  Future<void> put(OutboxEntry e) => db.into(db.outboxEntries).insertOnConflictUpdate(OutboxEntriesCompanion.insert(
        opId: e.opId,
        projectId: e.projectId,
        op: jsonEncode(e.op),
        state: e.state.name,
        label: e.label,
        subject: Value(e.subject),
        createdAt: e.createdAt,
        serverSeq: Value(e.serverSeq),
        winning: Value(e.winning.isEmpty ? null : e.winningJson),
        reason: Value(e.reason),
        notified: Value(e.notified),
      ));

  @override
  Future<void> remove(String opId) => (db.delete(db.outboxEntries)..where((t) => t.opId.equals(opId))).go();

  Future<Map<String, int>> pendingCounts() async {
    final count = db.outboxEntries.opId.count();
    final rows = await (db.selectOnly(db.outboxEntries)
          ..addColumns([db.outboxEntries.projectId, count])
          ..where(db.outboxEntries.state.equals('pending'))
          ..groupBy([db.outboxEntries.projectId]))
        .get();
    return {for (final r in rows) r.read(db.outboxEntries.projectId)!: r.read(count) ?? 0};
  }

  Stream<List<OutboxEntry>> watchOutbox(String pid) => (db.select(db.outboxEntries)
        ..where((t) => t.projectId.equals(pid))
        ..orderBy([(t) => OrderingTerm.desc(t.createdAt)]))
      .watch()
      .map((rows) => [for (final r in rows) _entry(r)]);

  // --- digests, manifests, values --------------------------------------------------------------

  Future<DigestSnapshot?> digest(String pid) async {
    final r = await (db.select(db.digests)..where((t) => t.projectId.equals(pid))).getSingleOrNull();
    if (r == null) return null;
    final d = ProjectDigest.parse(jsonDecode(r.body));
    if (d == null) return null;
    return DigestSnapshot(snapshotId: r.snapshotId, atSeq: r.atSeq, createdAt: r.createdAt, sha256: r.sha256, digest: d);
  }

  Future<String?> digestSha(String pid) async =>
      (await (db.select(db.digests)..where((t) => t.projectId.equals(pid))).getSingleOrNull())?.sha256;

  Future<void> putDigest(String pid, Snapshot snap, String sha256, String body) =>
      db.into(db.digests).insertOnConflictUpdate(DigestsCompanion.insert(
            projectId: pid,
            snapshotId: snap.snapshotId,
            atSeq: snap.atSeq,
            createdAt: snap.createdAt,
            sha256: sha256,
            body: body,
          ));

  /// The snapshot moved but its digest did not: keep the body, update the label.
  Future<void> touchDigest(String pid, Snapshot snap) =>
      (db.update(db.digests)..where((t) => t.projectId.equals(pid))).write(
          DigestsCompanion(snapshotId: Value(snap.snapshotId), atSeq: Value(snap.atSeq), createdAt: Value(snap.createdAt)));

  Future<SetState?> manifest(String pid, String setId) async {
    final r = await (db.select(db.manifests)..where((t) => t.projectId.equals(pid) & t.setId.equals(setId))).getSingleOrNull();
    return r == null ? null : SetState.fromJson(jsonDecode(r.body));
  }

  Future<int?> manifestRev(String pid, String setId) async =>
      (await (db.select(db.manifests)..where((t) => t.projectId.equals(pid) & t.setId.equals(setId))).getSingleOrNull())?.rev;

  Future<void> putManifest(String pid, String setId, SetState state) =>
      db.into(db.manifests).insertOnConflictUpdate(ManifestsCompanion.insert(
            projectId: pid,
            setId: setId,
            rev: state.rev,
            atSeq: state.atSeq,
            body: jsonEncode(state.toJson()),
          ));

  Future<List<SetState>> manifestsOf(String pid) async => [
        for (final r in await (db.select(db.manifests)..where((t) => t.projectId.equals(pid))).get())
          ?SetState.fromJson(jsonDecode(r.body)),
      ];

  Future<Map<String, Object?>?> json(String key) async {
    final v = await db.getValue(key);
    return v == null ? null : (jsonDecode(v) as Map).cast<String, Object?>();
  }

  Future<void> putJson(String key, Object value) => db.setValue(key, jsonEncode(value));
}
