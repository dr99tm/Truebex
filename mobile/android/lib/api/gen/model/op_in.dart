//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class OpIn {
  /// Returns a new [OpIn] instance.
  OpIn({
    this.action,
    required this.at,
    required this.author,
    required this.authorKind,
    required this.baseSeq,
    this.delta,
    this.deltaFormat,
    required this.kind,
    this.name = '',
    required this.opId,
    this.replicaId,
    this.touched = const [],
  });

  Object? action;

  String at;

  String author;

  String authorKind;

  /// Minimum value: 0
  int baseSeq;

  String? delta;

  String? deltaFormat;

  String kind;

  String name;

  String opId;

  String? replicaId;

  List<String> touched;

  @override
  bool operator ==(Object other) => identical(this, other) || other is OpIn &&
    other.action == action &&
    other.at == at &&
    other.author == author &&
    other.authorKind == authorKind &&
    other.baseSeq == baseSeq &&
    other.delta == delta &&
    other.deltaFormat == deltaFormat &&
    other.kind == kind &&
    other.name == name &&
    other.opId == opId &&
    other.replicaId == replicaId &&
    _deepEquality.equals(other.touched, touched);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (action == null ? 0 : action!.hashCode) +
    (at.hashCode) +
    (author.hashCode) +
    (authorKind.hashCode) +
    (baseSeq.hashCode) +
    (delta == null ? 0 : delta!.hashCode) +
    (deltaFormat == null ? 0 : deltaFormat!.hashCode) +
    (kind.hashCode) +
    (name.hashCode) +
    (opId.hashCode) +
    (replicaId == null ? 0 : replicaId!.hashCode) +
    (touched.hashCode);

  @override
  String toString() => 'OpIn[action=$action, at=$at, author=$author, authorKind=$authorKind, baseSeq=$baseSeq, delta=$delta, deltaFormat=$deltaFormat, kind=$kind, name=$name, opId=$opId, replicaId=$replicaId, touched=$touched]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.action != null) {
      json[r'action'] = this.action;
    } else {
      json[r'action'] = null;
    }
      json[r'at'] = this.at;
      json[r'author'] = this.author;
      json[r'author_kind'] = this.authorKind;
      json[r'base_seq'] = this.baseSeq;
    if (this.delta != null) {
      json[r'delta'] = this.delta;
    } else {
      json[r'delta'] = null;
    }
    if (this.deltaFormat != null) {
      json[r'delta_format'] = this.deltaFormat;
    } else {
      json[r'delta_format'] = null;
    }
      json[r'kind'] = this.kind;
      json[r'name'] = this.name;
      json[r'op_id'] = this.opId;
    if (this.replicaId != null) {
      json[r'replica_id'] = this.replicaId;
    } else {
      json[r'replica_id'] = null;
    }
      json[r'touched'] = this.touched;
    return json;
  }

  /// Returns a new [OpIn] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static OpIn? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'at'), 'Required key "OpIn[at]" is missing from JSON.');
        assert(json[r'at'] != null, 'Required key "OpIn[at]" has a null value in JSON.');
        assert(json.containsKey(r'author'), 'Required key "OpIn[author]" is missing from JSON.');
        assert(json[r'author'] != null, 'Required key "OpIn[author]" has a null value in JSON.');
        assert(json.containsKey(r'author_kind'), 'Required key "OpIn[author_kind]" is missing from JSON.');
        assert(json[r'author_kind'] != null, 'Required key "OpIn[author_kind]" has a null value in JSON.');
        assert(json.containsKey(r'base_seq'), 'Required key "OpIn[base_seq]" is missing from JSON.');
        assert(json[r'base_seq'] != null, 'Required key "OpIn[base_seq]" has a null value in JSON.');
        assert(json.containsKey(r'kind'), 'Required key "OpIn[kind]" is missing from JSON.');
        assert(json[r'kind'] != null, 'Required key "OpIn[kind]" has a null value in JSON.');
        assert(json.containsKey(r'op_id'), 'Required key "OpIn[op_id]" is missing from JSON.');
        assert(json[r'op_id'] != null, 'Required key "OpIn[op_id]" has a null value in JSON.');
        return true;
      }());

      return OpIn(
        action: mapValueOfType<Object>(json, r'action'),
        at: mapValueOfType<String>(json, r'at')!,
        author: mapValueOfType<String>(json, r'author')!,
        authorKind: mapValueOfType<String>(json, r'author_kind')!,
        baseSeq: mapValueOfType<int>(json, r'base_seq')!,
        delta: mapValueOfType<String>(json, r'delta'),
        deltaFormat: mapValueOfType<String>(json, r'delta_format'),
        kind: mapValueOfType<String>(json, r'kind')!,
        name: mapValueOfType<String>(json, r'name') ?? '',
        opId: mapValueOfType<String>(json, r'op_id')!,
        replicaId: mapValueOfType<String>(json, r'replica_id'),
        touched: json[r'touched'] is Iterable
            ? (json[r'touched'] as Iterable).cast<String>().toList(growable: false)
            : const [],
      );
    }
    return null;
  }

  static List<OpIn> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <OpIn>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = OpIn.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, OpIn> mapFromJson(dynamic json) {
    final map = <String, OpIn>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = OpIn.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of OpIn-objects as value to a dart map
  static Map<String, List<OpIn>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<OpIn>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = OpIn.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'at',
    'author',
    'author_kind',
    'base_seq',
    'kind',
    'op_id',
  };
}

