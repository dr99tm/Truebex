// replica_pull_pages_and_head: pulling ops-remote.json in pages gives head_seq
// 12 and the history in order; the deltas stay opaque.

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:truebex/api/api.dart';
import 'package:truebex/replica/replica.dart';

import 'helpers.dart';

void main() {
  const pid = 'a0000000000000000000000000000001';

  test('replica_pull_pages_and_head', () async {
    final db = memoryDb();
    final replica = Replica(db);
    final server = remoteOps();
    expect(server, hasLength(12));
    await replica.putProjectList([ProjectRecord.fromJson(FakeLog(projectId: pid).record(list: true))!]);

    // Pages of 5: 5 + 5 + 2, each answer naming the head and whether more follow.
    final asked = <int>[];
    final top = await replica.pullAll(pid, (after) async {
      asked.add(after);
      final rest = server.where((o) => (o['server_seq'] as int) > after).toList();
      return PullPage.fromJson({'ops': rest.take(5).toList(), 'head_seq': 12, 'more': rest.length > 5})!;
    });
    expect(asked, [0, 5, 10]);
    expect(top, 12);
    final project = (await replica.project(pid))!;
    expect(project.headSeq, 12);
    expect(project.pulledSeq, 12);
    expect(await replica.opCount(pid), 12);

    // The history reads the log newest first: who changed what, when.
    final history = await replica.history(pid, me: alexAuthor);
    expect([for (final h in history) h.serverSeq], [for (var i = 12; i >= 1; i--) i]);
    final fixtureOps = (fixture('ops-remote.json')['ops'] as List).cast<Map>();
    expect([for (final h in history.reversed) h.name], [for (final o in fixtureOps) o['name']]);
    expect(history.every((h) => h.author == samAuthor && !h.mine), isTrue);

    // The delta is kept exactly as it arrived (base64 text), never decoded.
    final row = await (db.select(db.ops)..where((t) => t.serverSeq.equals(1))).getSingle();
    expect(utf8.decode(row.delta!), fixtureOps.first['delta']);
    expect(row.deltaFormat, 'o5/38');

    // Pulling again asks only after what the phone holds and changes nothing.
    asked.clear();
    await replica.pullAll(pid, (after) async {
      asked.add(after);
      return PullPage.fromJson({'ops': [], 'head_seq': 12, 'more': false})!;
    });
    expect(asked, [12]);
    expect(await replica.opCount(pid), 12);
    await db.close();
  });

  test('a page delivered twice is stored once and the head never moves back', () async {
    final db = memoryDb();
    final replica = Replica(db);
    await replica.putProjectList([ProjectRecord.fromJson(FakeLog(projectId: pid).record(list: true))!]);
    final server = remoteOps();
    final page = PullPage.fromJson({'ops': server.take(3).toList(), 'head_seq': 12, 'more': true})!;
    await replica.storePage(pid, page);
    await replica.storePage(pid, page);
    expect(await replica.opCount(pid), 3);
    await replica.storePage(pid, PullPage.fromJson({'ops': [], 'head_seq': 3, 'more': false})!);
    expect((await replica.project(pid))!.headSeq, 12);
    await db.close();
  });

  test('a project no longer shared leaves the phone with its data', () async {
    final db = memoryDb();
    final replica = Replica(db);
    await replica.putProjectList([ProjectRecord.fromJson(FakeLog(projectId: pid).record(list: true))!]);
    await replica.storePage(pid, PullPage.fromJson({'ops': remoteOps().take(2).toList(), 'head_seq': 2, 'more': false})!);
    await replica.putProjectList([]);
    expect(await replica.project(pid), isNull);
    expect(await replica.opCount(pid), 0);
    await db.close();
  });
}
