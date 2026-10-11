// action_builder_matches_fixture: the Dart port of PF9's builder writes the
// operation of action-move.json field for field (the fixture PF9's self-test
// and the platform's pytest use too).

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:truebex/actions/actions.dart';
import 'package:truebex/actions/finishes.dart';
import 'package:truebex/api/api.dart';

import 'helpers.dart';

void main() {
  test('action_builder_matches_fixture', () {
    final fx = fixture('action-move.json');
    final want = (fx['op'] as Map).cast<String, Object?>();
    final action = (want['action'] as Map).cast<String, Object?>();
    final args = (action['args'] as Map).cast<String, Object?>();
    final op = buildActionOp(
      author: want['author'] as String,
      replicaId: fx['replica_id'] as String,
      baseSeq: want['base_seq'] as int,
      session: action['session'] as String,
      name: want['name'] as String,
      call: moveBy([for (final r in args['refs'] as List) r as String], [for (final v in args['by_mm'] as List) v as int]),
      opId: want['op_id'] as String,
      requestId: action['request_id'] as String,
      at: want['at'] as String,
    );
    final got = op.toJson();
    // Every field the builder writes equals the fixture's; the ones it leaves out are the
    // server's (server_seq) or empty for an action (delta, delta_format, restore).
    for (final entry in got.entries) {
      expect(jsonEncode(entry.value), jsonEncode(want[entry.key]), reason: entry.key);
    }
    expect(want.keys.toSet().difference(got.keys.toSet()), {'server_seq', 'delta', 'delta_format', 'restore'});
    expect(want['server_seq'], 0);
    expect(want['delta'], isNull);
    expect(want['delta_format'], isNull);
    expect(want['restore'], isNull);

    // The generated client sends it unchanged: the push body's operation is the fixture's.
    final wire = OpIn.fromJson(got)!.toJson();
    for (final key in got.keys) {
      expect(jsonEncode(wire[key]), jsonEncode(want[key]), reason: 'generated client: $key');
    }
  });

  test('touched is the sorted, unique set of refs in the arguments', () {
    const a = '0199c6a2e00070018000000000000002';
    const b = '0199c6a2e00070018000000000000001';
    expect(touchedOf({'refs': [a, b, a.toUpperCase()]}), [b, a]);
    expect(touchedOf({'target': a, 'replace': b, 'room': a, 'finish': {'kind': 'paint'}}), [b, a]);
    expect(touchedOf({'refs': ['not-an-id']}), isEmpty);
  });

  test('the light edits are the log-safe tools PF9 writes', () {
    const room = 'c0000000000000000000000000000001';
    const sofa = 'c0000000000000000000000000000002';
    const supplier = 'd0000000000000000000000000000001';
    final fill = fillFace(room, 'floor', floorFinishes.first.finish);
    expect(fill.tool, 'fill');
    expect(fill.args, {'target': room, 'face': 'floor', 'finish': floorFinishes.first.finish});
    expect(applyTheme(room, 'warm').args, {'theme': 'warm', 'target': room, 'keep_products': true});
    final swap = swapProduct(sofa, {'supplier_id': supplier, 'sku': 'SOFA', 'variant_id': 'oat'}, room: room);
    expect(swap.args['replace'], sofa);
    expect(swap.args['room'], room);
    expect(slideAlong(sofa, -50).args, {'refs': [sofa], 'along_mm': -50});
    for (final call in [fill, swap, applyTheme(room, 'warm'), slideAlong(sofa, 50), moveBy([sofa], [0, 250, 0])]) {
      final op = buildActionOp(author: alexAuthor, replicaId: samDesktop, baseSeq: 3, session: samDesktop, name: 'Edit', call: call);
      expect(op.toJson()['kind'], 'action');
      expect(isHex32(op.opId), isTrue);
      expect(RegExp(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$').hasMatch(op.at), isTrue);
    }
  });

  test('nudges follow the way the person looks (0 = north = +Y, 90 = east = +X)', () {
    expect(nudgeVector(0, Nudge.forward, 250), [0, 250, 0]);
    expect(nudgeVector(0, Nudge.right, 250), [250, 0, 0]);
    expect(nudgeVector(90, Nudge.forward, 50), [50, 0, 0]);
    expect(nudgeVector(90, Nudge.left, 50), [0, 50, 0]);
    expect(nudgeVector(180, Nudge.back, 250), [0, 250, 0]);
  });

  test('the builder refuses what agent-interface §5.7–5.11 refuses', () {
    ActionOp build(ToolCall call, {String author = alexAuthor, int base = 0}) =>
        buildActionOp(author: author, replicaId: samDesktop, baseSeq: base, session: samDesktop, name: 'x', call: call);
    const ref = 'c0000000000000000000000000000001';
    expect(() => build(moveBy([], [0, 0, 0])), throwsA(isA<ActionError>()));
    expect(() => build(const ToolCall('move', {'refs': [ref], 'by_mm': [0, 0, 0], 'along_mm': 5})), throwsA(isA<ActionError>()));
    expect(() => build(fillFace(ref, 'floor', {'kind': 'paint', 'colour': 'red'})), throwsA(isA<ActionError>()));
    expect(() => build(const ToolCall('delete', {'refs': [ref]})), throwsA(isA<ActionError>()));
    expect(() => build(const ToolCall('place', {'kind': 'wall', 'room': ref})), throwsA(isA<ActionError>()));
    expect(() => build(moveBy([ref], [0, 1, 0]), author: 'nobody'), throwsA(isA<ActionError>()));
    expect(() => build(moveBy([ref], [0, 1, 0]), base: -1), throwsA(isA<ActionError>()));
    expect(build(moveBy([ref], [0, 1, 0])).name.length, 1);
    final long = buildActionOp(author: alexAuthor, replicaId: samDesktop, baseSeq: 0, session: samDesktop, name: 'x' * 200, call: moveBy([ref], [0, 1, 0]));
    expect(long.name.length, nameMax);
  });

  test('the finishes are PF9 palette ids and objects', () {
    expect([for (final f in floorFinishes) f.id], ['oak', 'stone', 'concrete', 'sand']);
    expect([for (final f in wallFinishes) f.id], ['chalk', 'sage', 'lattice', 'brick']);
    expect(finishId({'kind': 'paint', 'colour': '#C8B79E', 'roughness': 0.6}, floorFinishes), 'sand');
    expect(finishId({'kind': 'paint', 'colour': '#000000'}, floorFinishes), 'custom');
    expect(finishId(null, floorFinishes), isNull);
  });
}
