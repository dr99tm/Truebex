// outbox_reconcile_rules: `accepted`, `duplicate`, `rejected` (+ winning) and
// `not_processed` handled per contract §6.3; a rejected op_id is never sent again.

import 'package:flutter_test/flutter_test.dart';
import 'package:truebex/actions/actions.dart';
import 'package:truebex/api/api.dart';
import 'package:truebex/outbox/outbox.dart';
import 'package:truebex/replica/replica.dart';

import 'helpers.dart';

const pid = 'a0000000000000000000000000000001';
const phone = 'e0000000000000000000000000000003';
const wall = '0199c6a2e00070018000000000000001';
const sofa = '0199c6a2e00070018000000000000099';

Map<String, Object?> op(String ref, {int base = 0}) =>
    buildActionOp(author: alexAuthor, replicaId: phone, baseSeq: base, session: phone, name: 'Move', call: moveBy([ref], [0, 50, 0])).toJson();

void main() {
  for (final store in ['memory', 'replica']) {
    group('outbox_reconcile_rules ($store)', () {
      late OutboxStore s;
      late Outbox outbox;
      setUp(() {
        s = store == 'memory' ? MemoryOutboxStore() : Replica(memoryDb());
        outbox = Outbox(s);
      });

      test('accepted, duplicate, rejected with the winner, not_processed', () async {
        final log = FakeLog();
        // Sam moved the wall on the desktop after the phone's base (0).
        log.append({'op_id': 'f0000000000000000000000000000001', 'author': samAuthor, 'author_kind': 'person', 'at': '2026-10-09T10:01:00.000Z',
          'touched': [wall], 'kind': 'delta', 'name': 'Move wall', 'base_seq': 0, 'delta': 'VEJYRA==', 'delta_format': 'o5/38'});
        final first = await outbox.add(pid, op(sofa, base: 1), label: 'Sofa', now: 1);
        final stale = await outbox.add(pid, op(wall), label: 'Wall', now: 2);
        final after = await outbox.add(pid, op(sofa, base: 1), label: 'Sofa again', now: 3);

        final out = await outbox.flush(pid, (replica, ops) async => PushAnswer.fromJson(log.push(replica, ops))!);
        // The head of the last answer: the second round's push of the rest.
        expect(out.head, 3);
        expect([for (final e in out.accepted) e.opId], [first.opId, after.opId]);
        expect([for (final e in out.rejected) e.opId], [stale.opId]);
        final rejected = (await s.get(stale.opId))!;
        expect(rejected.state, EntryState.rejected);
        expect(rejected.reason, 'conflict');
        expect(rejected.winning.single.author, samAuthor);
        expect(rejected.winning.single.name, 'Move wall');
        expect(rejected.winning.single.serverSeq, 1);
        expect((await s.get(first.opId))!.serverSeq, 2);
        // The rest of the stopped batch went out on the next round, unchanged, and was accepted.
        expect(log.pushedIds, [
          [first.opId, stale.opId, after.opId],
          [after.opId],
        ]);
        expect((await s.get(after.opId))!.state, EntryState.accepted);
        expect((await s.get(after.opId))!.serverSeq, 3);

        // Sent again (an answer lost on the way): duplicate keeps its number.
        final again = PushAnswer.fromJson(log.push(phone, [first.op]))!;
        expect(again.results.single.status, PushResultStatusEnum.duplicate);
        expect(applyResults([first], again).single.serverSeq, 2);

        // A rejected op_id is never sent again: not by a flush, not by a new add.
        log.pushedIds.clear();
        await outbox.flush(pid, (replica, ops) async => PushAnswer.fromJson(log.push(replica, ops))!);
        expect(log.pushedIds, isEmpty);
        await expectLater(outbox.add(pid, stale.op, label: 'Wall'), throwsStateError);
        await outbox.dismiss(stale.opId);
        expect((await s.get(stale.opId))!.state, EntryState.dismissed);
        await expectLater(outbox.add(pid, stale.op, label: 'Wall'), throwsStateError);
        await outbox.flush(pid, (replica, ops) async => PushAnswer.fromJson(log.push(replica, ops))!);
        expect(log.pushedIds, isEmpty);
      });

      test('not_processed stays pending with the same op_id and base_seq', () async {
        final a = await outbox.add(pid, op(sofa), label: 'A', now: 1);
        final b = await outbox.add(pid, op(wall), label: 'B', now: 2);
        final answer = PushAnswer.fromJson({
          'head_seq': 5,
          'results': [
            {'op_id': a.opId, 'status': 'accepted', 'server_seq': 5},
            {'op_id': b.opId, 'status': 'not_processed'},
          ],
        })!;
        final updated = applyResults([a, b], answer);
        expect(updated[0].state, EntryState.accepted);
        expect(updated[1].state, EntryState.pending);
        expect(updated[1].op, b.op);
        expect(updated[1].baseSeq, 0);
      });

      test('offline and 5xx keep everything pending; 422 fails the batch, never re-sent', () async {
        final a = await outbox.add(pid, op(sofa), label: 'A', now: 1);
        var calls = 0;
        var out = await outbox.flush(pid, (r, o) async {
          calls++;
          throw ApiFailure(0, 'network', 'offline');
        });
        expect(out.waiting, 1);
        expect((await s.get(a.opId))!.state, EntryState.pending);
        out = await outbox.flush(pid, (r, o) async {
          calls++;
          throw ApiFailure(503, 'unavailable', 'busy');
        });
        expect(out.waiting, 1);
        expect((await s.get(a.opId))!.state, EntryState.pending);
        out = await outbox.flush(pid, (r, o) async {
          calls++;
          throw ApiFailure(422, 'validation_failed', 'ops[0].touched: sorted and unique');
        });
        expect(out.failed.single.opId, a.opId);
        expect((await s.get(a.opId))!.state, EntryState.failed);
        final before = calls;
        await outbox.flush(pid, (r, o) async {
          calls++;
          throw StateError('must not be called');
        });
        expect(calls, before);
      });

      test('at most 200 operations a request, in order', () async {
        final ids = <String>[];
        for (var i = 0; i < 450; i++) {
          ids.add((await outbox.add(pid, op(sofa), label: 'n$i', now: i)).opId);
        }
        final sizes = <int>[];
        final log = FakeLog();
        await outbox.flush(pid, (replica, ops) async {
          sizes.add(ops.length);
          return PushAnswer.fromJson(log.push(replica, ops))!;
        });
        expect(sizes, [200, 200, 50]);
        expect(log.ops.length, 450);
        expect([for (final o in log.ops) o['op_id']], ids);
        // The newest accepted edits stay listed; older ones leave the outbox (they are in the log).
        expect((await s.list(pid)).length, keepAccepted);
      });
    });
  }

  test('takeUnnotified returns each rejection once', () async {
    final outbox = Outbox(MemoryOutboxStore());
    final e = await outbox.add(pid, op(wall), label: 'Wall');
    await outbox.store.put(e.copyWith(state: EntryState.rejected, winning: const [Winner(opId: 'x', serverSeq: 1, author: samAuthor, name: 'Move wall')]));
    expect((await outbox.takeUnnotified(pid)).single.opId, e.opId);
    expect(await outbox.takeUnnotified(pid), isEmpty);
  });
}
