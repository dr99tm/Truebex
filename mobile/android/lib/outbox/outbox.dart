// The outbox of the phone's own `action` operations (contract project-log §6.3
// and §8 for a light client), the rules of PF9's src/viewer/outbox.ts:
//
// * pending operations go out in order, at most 200 a request, one replica id
//   per request;
// * `accepted` and `duplicate` are done (the server's number is kept);
// * `rejected` is shown with the operations that won, in the history and as a
//   notification, and is never sent again — a rejected op_id never re-enters
//   the outbox;
// * `not_processed` (the rest of a stopped batch) stays pending, unchanged —
//   same op_id, same base_seq — and goes out next time, so a stale edit of
//   something another replica changed is rejected and shown, never applied
//   silently;
// * network errors and 408 / 429 / 5xx keep everything pending for the next
//   sync; another 4xx fails the batch, which is never retried as sent.

import 'dart:convert';

import '../api/api.dart';

const maxBatch = 200;

/// Accepted edits kept per project for the list of recent edits.
const keepAccepted = 50;

/// `dismissed`: a rejected or failed edit the person cleared from the history,
/// kept as a tombstone so its op_id can never enter the outbox again.
enum EntryState { pending, accepted, rejected, failed, dismissed }

class Winner {
  const Winner({required this.opId, required this.serverSeq, required this.author, required this.name});

  final String opId;
  final int serverSeq;
  final String author;
  final String name;

  Map<String, Object?> toJson() => {'op_id': opId, 'server_seq': serverSeq, 'author': author, 'name': name};

  static Winner fromJson(Map<String, Object?> j) => Winner(
        opId: j['op_id'] as String,
        serverSeq: (j['server_seq'] as num).toInt(),
        author: j['author'] as String,
        name: j['name'] as String,
      );
}

class OutboxEntry {
  const OutboxEntry({
    required this.opId,
    required this.projectId,
    required this.op,
    required this.state,
    required this.label,
    required this.createdAt,
    this.subject,
    this.serverSeq,
    this.winning = const [],
    this.reason,
    this.notified = false,
  });

  final String opId;
  final String projectId;

  /// The operation exactly as built (and as sent on every try).
  final Map<String, Object?> op;
  final EntryState state;
  final String label;
  final String? subject;
  final int createdAt;
  final int? serverSeq;
  final List<Winner> winning;
  final String? reason;
  final bool notified;

  String get replicaId => op['replica_id'] as String;
  int get baseSeq => (op['base_seq'] as num).toInt();

  OutboxEntry copyWith({EntryState? state, int? serverSeq, List<Winner>? winning, String? reason, bool? notified}) =>
      OutboxEntry(
        opId: opId,
        projectId: projectId,
        op: op,
        state: state ?? this.state,
        label: label,
        subject: subject,
        createdAt: createdAt,
        serverSeq: serverSeq ?? this.serverSeq,
        winning: winning ?? this.winning,
        reason: reason ?? this.reason,
        notified: notified ?? this.notified,
      );

  String get winningJson => jsonEncode([for (final w in winning) w.toJson()]);
}

/// Where the outbox lives (the replica database on the phone).
abstract class OutboxStore {
  /// Every entry of the project, oldest first.
  Future<List<OutboxEntry>> list(String projectId);
  Future<void> put(OutboxEntry entry);
  Future<void> remove(String opId);
  Future<OutboxEntry?> get(String opId);
}

/// A push answered as a whole with an error; `retry` says whether sending it again may work.
class PushFailure implements Exception {
  PushFailure(this.failure);
  final ApiFailure failure;
  bool get retry => failure.retryable || failure.unauthenticated;
}

typedef PushFn = Future<PushAnswer> Function(String replicaId, List<Map<String, Object?>> ops);

class FlushOutcome {
  int? head;
  final List<OutboxEntry> accepted = [];
  final List<OutboxEntry> rejected = [];
  final List<OutboxEntry> failed = [];

  /// Still pending: offline, or the server asked to retry later.
  int waiting = 0;
  ApiFailure? error;
}

/// Apply 5.6's per-operation results to the batch they answer. Pure.
List<OutboxEntry> applyResults(List<OutboxEntry> batch, PushAnswer answer) {
  final byId = {for (final r in answer.results) r.opId: r};
  return [
    for (final entry in batch)
      switch (byId[entry.opId]) {
        null => entry,
        final r when r.status == PushResultStatusEnum.notProcessed => entry,
        final r when r.status == PushResultStatusEnum.accepted || r.status == PushResultStatusEnum.duplicate =>
          entry.copyWith(state: EntryState.accepted, serverSeq: r.serverSeq),
        final r => entry.copyWith(
            state: EntryState.rejected,
            reason: r.reason ?? 'conflict',
            winning: [
              for (final w in r.winning ?? const <Operation>[])
                Winner(opId: w.opId, serverSeq: w.serverSeq, author: w.author, name: w.name),
            ],
          ),
      },
  ];
}

class Outbox {
  Outbox(this.store);

  final OutboxStore store;
  final Map<String, Future<FlushOutcome>> _flushing = {};

  /// Queue a new operation. An op_id the outbox has seen (sent, accepted or
  /// rejected) is refused: a rejected one is never sent again.
  Future<OutboxEntry> add(String projectId, Map<String, Object?> op, {required String label, String? subject, int? now}) async {
    final opId = op['op_id'] as String;
    if (await store.get(opId) != null) throw StateError('op_id $opId is already in the outbox');
    final entry = OutboxEntry(
      opId: opId,
      projectId: projectId,
      op: op,
      state: EntryState.pending,
      label: label,
      subject: subject,
      createdAt: now ?? DateTime.now().millisecondsSinceEpoch,
    );
    await store.put(entry);
    return entry;
  }

  Future<List<OutboxEntry>> pending(String projectId) async =>
      (await store.list(projectId)).where((e) => e.state == EntryState.pending).toList();

  /// Send every pending operation of the project; one flush at a time per project.
  Future<FlushOutcome> flush(String projectId, PushFn push) =>
      // A block body: returning the removed future from whenComplete would wait on itself.
      _flushing[projectId] ??= _run(projectId, push).whenComplete(() {
        _flushing.remove(projectId);
      });

  Future<FlushOutcome> _run(String projectId, PushFn push) async {
    final out = FlushOutcome();
    for (var round = 0; round < 1000; round++) {
      final pending = await this.pending(projectId);
      if (pending.isEmpty) break;
      final replica = pending.first.replicaId;
      final batch = pending.where((e) => e.replicaId == replica).take(maxBatch).toList();
      PushAnswer answer;
      try {
        answer = await push(replica, [for (final e in batch) e.op]);
      } on ApiFailure catch (failure) {
        out.error = failure;
        if (failure.retryable || failure.unauthenticated) {
          out.waiting = pending.length;
          return out;
        }
        // 409, 422 and the like: never retried as sent.
        for (final e in batch) {
          final failed = e.copyWith(state: EntryState.failed, reason: failure.message);
          await store.put(failed);
          out.failed.add(failed);
        }
        continue;
      }
      out.head = answer.headSeq;
      var progressed = false;
      for (final e in applyResults(batch, answer)) {
        if (e.state == EntryState.pending) continue;
        progressed = true;
        await store.put(e);
        (e.state == EntryState.accepted ? out.accepted : out.rejected).add(e);
      }
      if (!progressed) {
        out.waiting = pending.length;
        break;
      }
    }
    await _prune(projectId);
    return out;
  }

  Future<void> _prune(String projectId) async {
    final accepted = (await store.list(projectId)).where((e) => e.state == EntryState.accepted).toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    for (final e in accepted.skip(keepAccepted)) {
      await store.remove(e.opId);
    }
  }

  /// Rejections not yet shown as a notification; marks them shown.
  Future<List<OutboxEntry>> takeUnnotified(String projectId) async {
    final found = (await store.list(projectId)).where((e) => e.state == EntryState.rejected && !e.notified).toList();
    for (final e in found) {
      await store.put(e.copyWith(notified: true));
    }
    return found;
  }

  /// The person dismissed a rejected or failed edit from the history.
  Future<void> dismiss(String opId) async {
    final e = await store.get(opId);
    if (e != null && (e.state == EntryState.rejected || e.state == EntryState.failed)) {
      await store.put(e.copyWith(state: EntryState.dismissed, notified: true));
    }
  }
}

/// An in-memory store (tests).
class MemoryOutboxStore implements OutboxStore {
  final Map<String, OutboxEntry> rows = {};

  @override
  Future<List<OutboxEntry>> list(String projectId) async =>
      rows.values.where((e) => e.projectId == projectId).toList()..sort((a, b) => a.createdAt.compareTo(b.createdAt));

  @override
  Future<void> put(OutboxEntry entry) async => rows[entry.opId] = entry;

  @override
  Future<void> remove(String opId) async => rows.remove(opId);

  @override
  Future<OutboxEntry?> get(String opId) async => rows[opId];
}
