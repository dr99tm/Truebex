// The light client's edits as project-log `action` operations: a Dart port of
// PF9's builder (src/viewer/actions.ts; contract project-log §6.2, the action
// of agent-interface §6.4). The phone never writes a delta: each edit names one
// log-safe tool with its arguments, and every kernel replica applies it through
// the same tool at its server_seq.
//
// `touched` is the sorted, unique set of entity refs in the arguments (§6.2);
// `name` is the undo-step name the desktop shows. Checked against the contract
// fixture action-move.json (test/action_builder_test.dart), as PF9's self-test is.

import 'dart:math';

/// Three numbers in doc millimetres (+Y north, +Z up).
typedef P3 = List<int>;

const nameMax = 80;
final _hex32 = RegExp(r'^[0-9a-f]{32}$');
final _colour = RegExp(r'^#[0-9A-Fa-f]{6}$');
const _refKeys = ['refs', 'target', 'host', 'room', 'replace'];
const _maxMm = 1000000;

bool isHex32(Object? value) => value is String && _hex32.hasMatch(value);

final Random _random = Random.secure();

/// 32 lowercase hex from the platform's secure random source (op ids, replica ids).
String hex32([Random? random]) {
  final r = random ?? _random;
  final out = StringBuffer();
  for (var i = 0; i < 16; i++) {
    out.write(r.nextInt(256).toRadixString(16).padLeft(2, '0'));
  }
  return out.toString();
}

String _two(int n) => n.toString().padLeft(2, '0');

/// RFC 3339 UTC with milliseconds and `Z` (2026-10-09T12:00:00.000Z).
String rfc3339ms(DateTime at) {
  final u = at.toUtc();
  return '${u.year.toString().padLeft(4, '0')}-${_two(u.month)}-${_two(u.day)}'
      'T${_two(u.hour)}:${_two(u.minute)}:${_two(u.second)}.${u.millisecond.toString().padLeft(3, '0')}Z';
}

class ActionError implements Exception {
  ActionError(this.message);
  final String message;
  @override
  String toString() => 'action: $message';
}

Never _fail(String message) => throw ActionError(message);

/// One log-safe tool and its arguments (agent-interface §5.7–5.11).
class ToolCall {
  const ToolCall(this.tool, this.args);
  final String tool;
  final Map<String, Object?> args;
}

/// Every entity ref in a tool's arguments, sorted and unique: the operation's `touched`.
List<String> touchedOf(Map<String, Object?> args) {
  final refs = <String>{};
  for (final key in _refKeys) {
    final value = args[key];
    for (final v in value is List ? value : [value]) {
      if (v is String && _hex32.hasMatch(v.toLowerCase())) refs.add(v.toLowerCase());
    }
  }
  return refs.toList()..sort();
}

bool _finiteMm(Object? v) => v is num && v.isFinite && v.abs() <= _maxMm;
bool _isP3(Object? v) => v is List && v.length == 3 && v.every(_finiteMm);

/// The checks of agent-interface §5.7–5.11 a light client can make without the model.
void validateCall(ToolCall call) {
  final a = call.args;
  bool refsOk(Object? refs) => refs is List && refs.isNotEmpty && refs.length <= 100 && refs.every(isHex32);
  switch (call.tool) {
    case 'move':
      if (!refsOk(a['refs'])) _fail('move.refs: 1 to 100 entity ids');
      final given = ['by_mm', 'to_mm', 'along_mm', 'rotate_deg'].where((k) => a[k] != null).length;
      if (given != 1) _fail('move: exactly one of by_mm, to_mm, along_mm, rotate_deg');
      if (a['by_mm'] != null && !_isP3(a['by_mm'])) _fail('move.by_mm: three numbers (mm)');
      if (a['to_mm'] != null && (!_isP3(a['to_mm']) || (a['refs'] as List).length != 1)) {
        _fail('move.to_mm: one ref, three numbers');
      }
      if (a['along_mm'] != null && !_finiteMm(a['along_mm'])) _fail('move.along_mm: a number (mm)');
      final rotate = a['rotate_deg'];
      if (rotate != null && !(rotate is num && rotate.abs() <= 360)) _fail('move.rotate_deg: -360 to 360');
    case 'fill':
      if (!isHex32(a['target'])) _fail('fill.target: an entity id');
      final f = a['finish'];
      if (f is! Map || !const ['paint', 'wallpaper', 'pattern3d', 'none'].contains(f['kind'])) _fail('fill.finish.kind');
      final colour = f['colour'];
      if (colour != null && !(colour is String && _colour.hasMatch(colour))) _fail('fill.finish.colour: #RRGGBB');
      final rough = f['roughness'];
      if (rough != null && !(rough is num && rough >= 0 && rough <= 1)) _fail('fill.finish.roughness: 0 to 1');
      final texture = f['texture'];
      if (texture != null && !(texture is String && texture.length <= 120)) _fail('fill.finish.texture: at most 120 characters');
    case 'apply_theme':
      if (!isHex32(a['target'])) _fail('apply_theme.target: an entity id');
      final theme = a['theme'];
      if (theme is! String || theme.isEmpty || theme.length > 120) _fail('apply_theme.theme: 1 to 120 characters');
    case 'place':
      if (a['kind'] != 'product') _fail('place: only products travel in the log from a light client');
      final p = a['product'];
      if (p is! Map ||
          !isHex32(p['supplier_id']) ||
          p['sku'] is! String ||
          (p['sku'] as String).isEmpty ||
          (p['sku'] as String).length > 64 ||
          p['variant_id'] is! String ||
          (p['variant_id'] as String).isEmpty ||
          (p['variant_id'] as String).length > 64) {
        _fail('place.product: supplier_id, sku, variant_id');
      }
      if (a['replace'] != null && !isHex32(a['replace'])) _fail('place.replace: an entity id');
      if (a['room'] != null && !isHex32(a['room'])) _fail('place.room: an entity id');
      if (a['room'] == null && a['at_mm'] == null && a['replace'] == null) _fail('place: room, at_mm or replace');
    default:
      _fail('not a log-safe tool');
  }
}

/// An `action` operation, ready for 5.6 (`POST /projects/{pid}/ops`).
class ActionOp {
  const ActionOp({
    required this.opId,
    required this.author,
    required this.at,
    required this.replicaId,
    required this.baseSeq,
    required this.name,
    required this.touched,
    required this.action,
  });

  final String opId;
  final String author;
  final String at;
  final String replicaId;
  final int baseSeq;
  final String name;
  final List<String> touched;

  /// `{tool, args, permission, session, request_id}`.
  final Map<String, Object?> action;

  String get tool => action['tool'] as String;

  Map<String, Object?> toJson() => {
        'op_id': opId,
        'author': author,
        'author_kind': 'person',
        'at': at,
        'replica_id': replicaId,
        'base_seq': baseSeq,
        'kind': 'action',
        'name': name,
        'touched': touched,
        'action': action,
      };

  static ActionOp fromJson(Map<String, Object?> json) => ActionOp(
        opId: json['op_id'] as String,
        author: json['author'] as String,
        at: json['at'] as String,
        replicaId: json['replica_id'] as String,
        baseSeq: (json['base_seq'] as num).toInt(),
        name: json['name'] as String,
        touched: [for (final t in json['touched'] as List) t as String],
        action: Map<String, Object?>.from(json['action'] as Map),
      );
}

String _clip(String name) {
  final runes = name.trim().runes.toList();
  return String.fromCharCodes(runes.take(nameMax));
}

/// One `action` operation built from a tool call (the person's author id, this
/// installation's replica id for the project, the head it had seen).
ActionOp buildActionOp({
  required String author,
  required String replicaId,
  required int baseSeq,
  required String session,
  required String name,
  required ToolCall call,
  String? opId,
  String? requestId,
  Object? at,
}) {
  final a = author.toLowerCase();
  final replica = replicaId.toLowerCase();
  final sess = session.toLowerCase();
  if (!isHex32(a)) _fail("author: 32 hex (the person's author_id)");
  if (!isHex32(replica)) _fail('replica_id: 32 hex');
  if (!isHex32(sess)) _fail('session: 32 hex');
  if (baseSeq < 0) _fail('base_seq: 0 or more');
  validateCall(call);
  final op = (opId ?? hex32()).toLowerCase();
  final request = (requestId ?? hex32()).toLowerCase();
  if (!isHex32(op) || !isHex32(request)) _fail('op_id, request_id: 32 hex');
  final when = at is String ? at : rfc3339ms(at is DateTime ? at : DateTime.now());
  return ActionOp(
    opId: op,
    author: a,
    at: when,
    replicaId: replica,
    baseSeq: baseSeq,
    name: _clip(name),
    touched: touchedOf(call.args),
    action: {'tool': call.tool, 'args': call.args, 'permission': 'edit', 'session': sess, 'request_id': request},
  );
}

// --- the light edits ---------------------------------------------------------------------

enum Nudge { left, right, forward, back }

/// A step in doc millimetres relative to where the person looks (`bearingDeg`,
/// compass: 0 = north = doc +Y, 90 = east = doc +X), rounded to whole mm.
P3 nudgeVector(double bearingDeg, Nudge dir, int stepMm) {
  final b = bearingDeg * pi / 180;
  final forward = [sin(b), cos(b)];
  final right = [cos(b), -sin(b)];
  final v = switch (dir) {
    Nudge.forward => forward,
    Nudge.back => [-forward[0], -forward[1]],
    Nudge.right => right,
    Nudge.left => [-right[0], -right[1]],
  };
  return [(v[0] * stepMm).round(), (v[1] * stepMm).round(), 0];
}

ToolCall moveBy(List<String> refs, P3 by) => ToolCall('move', {'refs': refs, 'by_mm': by});

ToolCall slideAlong(String ref, int along) => ToolCall('move', {
      'refs': [ref],
      'along_mm': along,
    });

ToolCall fillFace(String target, String face, Map<String, Object?> finish) =>
    ToolCall('fill', {'target': target, 'face': face, 'finish': finish});

ToolCall applyTheme(String room, String theme) =>
    ToolCall('apply_theme', {'theme': theme, 'target': room, 'keep_products': true});

ToolCall swapProduct(String replace, Map<String, String> product, {String? room}) => ToolCall('place', {
      'kind': 'product',
      'product': product,
      'replace': replace,
      'room': ?room,
    });

/// Where one point lies seen from another: compass bearing and pitch, a little
/// below the horizon (a hotspot marks the floor of the other room). As PF9's
/// `bearingTo` (src/viewer/orientation.ts).
({double yawDeg, double pitchDeg}) bearingTo(List<num> from, List<num> to) {
  final dx = to[0] - from[0];
  final dy = to[1] - from[1];
  final dz = (to.length > 2 ? to[2] : 0) - (from.length > 2 ? from[2] : 0);
  final flat = sqrt(dx * dx + dy * dy);
  final yaw = (atan2(dx, dy) * 180 / pi + 360) % 360;
  final pitch = flat > 0 ? atan2(dz, flat) * 180 / pi - 8 : 0.0;
  return (yawDeg: yaw, pitchDeg: pitch.clamp(-60, 60).toDouble());
}
