// action_builder_matches_fixture: the Dart port of PF9's builder writes the
// operation of the app's action-move.json (CL1, project-log 1.1.0): a move of the
// picked wall gives its tool, args (refs `<kind>#<id>`), permission and touched
// field for field (the fixture PF9's self-test and the platform's pytest use too).

import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:truebex/actions/actions.dart';
import 'package:truebex/actions/finishes.dart';
import 'package:truebex/api/api.dart';

import 'helpers.dart';

void main() {
  test('action_builder_matches_fixture', () {
    final want = fixture('action-move.json');
    final action = (want['action'] as Map).cast<String, Object?>();
    final wall = (want['touched'] as List).single as String;
    const session = '5e55000000000000000000000000000a';
    // Author, op_id, replica_id and at are per client: the fixture's are passed in.
    final op = buildActionOp(
      author: want['author'] as String,
      replicaId: want['replica_id'] as String,
      baseSeq: want['base_seq'] as int,
      session: session,
      name: want['name'] as String,
      call: moveBy([ref(DigestKinds.wall, wall)], [0, 600, 0]),
      opId: want['op_id'] as String,
      at: want['at'] as String,
    );
    final got = op.toJson();
    expect((got['action'] as Map)['args'], {
      'refs': ['wall#$wall'],
      'by_mm': [0, 600, 0],
    });
    expect(got['touched'], [wall]);
    // Every other field the builder writes equals the fixture's; the one it leaves out is the server's.
    for (final entry in got.entries.where((e) => e.key != 'action')) {
      expect(jsonEncode(entry.value), jsonEncode(want[entry.key]), reason: entry.key);
    }
    expect(want.keys.toSet().difference(got.keys.toSet()), {'server_seq'});
    expect(want['server_seq'], 0);
    // The action: tool, args and permission byte for byte; session and request_id are a live
    // call's (agent-interface §6.4), which the app's log action carries neither of.
    final built = Map<String, Object?>.from(got['action'] as Map);
    expect(built.remove('session'), session);
    expect(isHex32(built.remove('request_id')), isTrue);
    expect(jsonEncode(built), jsonEncode(action));
    expect(action.containsKey('session'), isFalse);

    // The generated client sends it unchanged: the push body's operation is what the builder wrote.
    final wire = OpIn.fromJson(got)!.toJson();
    for (final key in got.keys) {
      expect(jsonEncode(wire[key]), jsonEncode(got[key]), reason: 'generated client: $key');
    }
    // And reads the app's own action back from a pull (no session, no request_id).
    final pulled = Operation.fromJson({...want, 'server_seq': 13, 'delta': null, 'delta_format': null, 'restore': null})!;
    expect(pulled.action!.tool, 'move');
    expect(pulled.action!.session, isNull);
    expect(pulled.action!.args, action['args']);
  });

  test('a pick with no kind is refused, never sent as a bare id', () {
    const wall = 'dc643577cfb582fabd0d7f9edef6b30d';
    ActionOp build(ToolCall call) =>
        buildActionOp(author: alexAuthor, replicaId: samDesktop, baseSeq: 0, session: samDesktop, name: 'x', call: call);
    expect(() => build(moveBy([wall], [0, 600, 0])), throwsA(isA<ActionError>()));
    expect(() => build(moveBy(['sofa#$wall'], [0, 600, 0])), throwsA(isA<ActionError>()));
    expect(() => build(fillFace(wall, 'left', {'kind': 'paint', 'colour': '#C8B79E'})), throwsA(isA<ActionError>()));
    expect(() => build(applyTheme(wall, 'warm')), throwsA(isA<ActionError>()));
    expect(refId('WALL#${wall.toUpperCase()}'), wall);
    expect(refId(wall), isNull);
    expect(refId('wall#nope'), isNull);
    expect(ref(DigestKinds.product, wall), 'object#$wall');
    expect(ref(DigestKinds.opening, wall), 'opening#$wall');
  });

  test('touched is the sorted, unique set of the refs\' ids in the arguments', () {
    const a = '0199c6a2e00070018000000000000002';
    const b = '0199c6a2e00070018000000000000001';
    expect(touchedOf({'refs': [ref('wall', a), ref('wall', b), ref('wall', a).toUpperCase()]}), [b, a]);
    expect(touchedOf({'target': ref('room', a), 'replace': ref('object', b), 'room': ref('room', a), 'finish': {'kind': 'paint'}}), [b, a]);
    expect(touchedOf({'refs': ['not-an-id', a]}), isEmpty, reason: 'a bare id is not a ref');
  });

  test('the light edits are the log-safe tools PF9 writes', () {
    final room = ref(DigestKinds.room, 'c0000000000000000000000000000001');
    final sofa = ref(DigestKinds.product, 'c0000000000000000000000000000002');
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
      expect(op.touched.every(isHex32), isTrue);
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
    const wall = 'wall#c0000000000000000000000000000001';
    expect(() => build(moveBy([], [0, 0, 0])), throwsA(isA<ActionError>()));
    expect(() => build(const ToolCall('move', {'refs': [wall], 'by_mm': [0, 0, 0], 'along_mm': 5})), throwsA(isA<ActionError>()));
    expect(() => build(fillFace(wall, 'floor', {'kind': 'paint', 'colour': 'red'})), throwsA(isA<ActionError>()));
    expect(() => build(const ToolCall('delete', {'refs': [wall]})), throwsA(isA<ActionError>()));
    expect(() => build(const ToolCall('place', {'kind': 'wall', 'room': wall})), throwsA(isA<ActionError>()));
    expect(() => build(moveBy([wall], [0, 1, 0]), author: 'nobody'), throwsA(isA<ActionError>()));
    expect(() => build(moveBy([wall], [0, 1, 0]), base: -1), throwsA(isA<ActionError>()));
    expect(build(moveBy([wall], [0, 1, 0])).name.length, 1);
    final long = buildActionOp(author: alexAuthor, replicaId: samDesktop, baseSeq: 0, session: samDesktop, name: 'x' * 200, call: moveBy([wall], [0, 1, 0]));
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
