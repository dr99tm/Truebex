//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class Operation {
  /// Returns a new [Operation] instance.
  Operation({
    required this.action,
    required this.at,
    required this.author,
    required this.authorKind,
    required this.baseSeq,
    required this.delta,
    required this.deltaFormat,
    required this.kind,
    required this.name,
    required this.opId,
    required this.replicaId,
    required this.restore,
    required this.serverSeq,
    this.touched = const [],
  });

  OperationAction? action;

  String at;

  String author;

  OperationAuthorKindEnum authorKind;

  int baseSeq;

  String? delta;

  String? deltaFormat;

  OperationKindEnum kind;

  String name;

  String opId;

  String replicaId;

  Object? restore;

  int serverSeq;

  List<String> touched;

  @override
  bool operator ==(Object other) => identical(this, other) || other is Operation &&
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
    other.restore == restore &&
    other.serverSeq == serverSeq &&
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
    (replicaId.hashCode) +
    (restore == null ? 0 : restore!.hashCode) +
    (serverSeq.hashCode) +
    (touched.hashCode);

  @override
  String toString() => 'Operation[action=$action, at=$at, author=$author, authorKind=$authorKind, baseSeq=$baseSeq, delta=$delta, deltaFormat=$deltaFormat, kind=$kind, name=$name, opId=$opId, replicaId=$replicaId, restore=$restore, serverSeq=$serverSeq, touched=$touched]';

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
      json[r'replica_id'] = this.replicaId;
    if (this.restore != null) {
      json[r'restore'] = this.restore;
    } else {
      json[r'restore'] = null;
    }
      json[r'server_seq'] = this.serverSeq;
      json[r'touched'] = this.touched;
    return json;
  }

  /// Returns a new [Operation] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static Operation? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'action'), 'Required key "Operation[action]" is missing from JSON.');
        assert(json.containsKey(r'at'), 'Required key "Operation[at]" is missing from JSON.');
        assert(json[r'at'] != null, 'Required key "Operation[at]" has a null value in JSON.');
        assert(json.containsKey(r'author'), 'Required key "Operation[author]" is missing from JSON.');
        assert(json[r'author'] != null, 'Required key "Operation[author]" has a null value in JSON.');
        assert(json.containsKey(r'author_kind'), 'Required key "Operation[author_kind]" is missing from JSON.');
        assert(json[r'author_kind'] != null, 'Required key "Operation[author_kind]" has a null value in JSON.');
        assert(json.containsKey(r'base_seq'), 'Required key "Operation[base_seq]" is missing from JSON.');
        assert(json[r'base_seq'] != null, 'Required key "Operation[base_seq]" has a null value in JSON.');
        assert(json.containsKey(r'delta'), 'Required key "Operation[delta]" is missing from JSON.');
        assert(json.containsKey(r'delta_format'), 'Required key "Operation[delta_format]" is missing from JSON.');
        assert(json.containsKey(r'kind'), 'Required key "Operation[kind]" is missing from JSON.');
        assert(json[r'kind'] != null, 'Required key "Operation[kind]" has a null value in JSON.');
        assert(json.containsKey(r'name'), 'Required key "Operation[name]" is missing from JSON.');
        assert(json[r'name'] != null, 'Required key "Operation[name]" has a null value in JSON.');
        assert(json.containsKey(r'op_id'), 'Required key "Operation[op_id]" is missing from JSON.');
        assert(json[r'op_id'] != null, 'Required key "Operation[op_id]" has a null value in JSON.');
        assert(json.containsKey(r'replica_id'), 'Required key "Operation[replica_id]" is missing from JSON.');
        assert(json[r'replica_id'] != null, 'Required key "Operation[replica_id]" has a null value in JSON.');
        assert(json.containsKey(r'restore'), 'Required key "Operation[restore]" is missing from JSON.');
        assert(json.containsKey(r'server_seq'), 'Required key "Operation[server_seq]" is missing from JSON.');
        assert(json[r'server_seq'] != null, 'Required key "Operation[server_seq]" has a null value in JSON.');
        assert(json.containsKey(r'touched'), 'Required key "Operation[touched]" is missing from JSON.');
        assert(json[r'touched'] != null, 'Required key "Operation[touched]" has a null value in JSON.');
        return true;
      }());

      return Operation(
        action: OperationAction.fromJson(json[r'action']),
        at: mapValueOfType<String>(json, r'at')!,
        author: mapValueOfType<String>(json, r'author')!,
        authorKind: OperationAuthorKindEnum.fromJson(json[r'author_kind'])!,
        baseSeq: mapValueOfType<int>(json, r'base_seq')!,
        delta: mapValueOfType<String>(json, r'delta'),
        deltaFormat: mapValueOfType<String>(json, r'delta_format'),
        kind: OperationKindEnum.fromJson(json[r'kind'])!,
        name: mapValueOfType<String>(json, r'name')!,
        opId: mapValueOfType<String>(json, r'op_id')!,
        replicaId: mapValueOfType<String>(json, r'replica_id')!,
        restore: mapValueOfType<Object>(json, r'restore'),
        serverSeq: mapValueOfType<int>(json, r'server_seq')!,
        touched: json[r'touched'] is Iterable
            ? (json[r'touched'] as Iterable).cast<String>().toList(growable: false)
            : const [],
      );
    }
    return null;
  }

  static List<Operation> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <Operation>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = Operation.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, Operation> mapFromJson(dynamic json) {
    final map = <String, Operation>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = Operation.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of Operation-objects as value to a dart map
  static Map<String, List<Operation>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<Operation>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = Operation.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'action',
    'at',
    'author',
    'author_kind',
    'base_seq',
    'delta',
    'delta_format',
    'kind',
    'name',
    'op_id',
    'replica_id',
    'restore',
    'server_seq',
    'touched',
  };
}


enum OperationAuthorKindEnum {
  person._(r'person'),
  agent._(r'agent'),
  ;

  /// Instantiate a new enum with the provided value.
  const OperationAuthorKindEnum._(this._value);

  /// The underlying value of this enum member.
  final String _value;

  @override
  String toString() => _value;

  /// Encodes this enum as a value suitable for JSON.
  String toJson() => _value;

  /// Returns the instance of [OperationAuthorKindEnum] that was successfully decoded
  /// from the passed [value] on success, null otherwise.
  static OperationAuthorKindEnum? fromJson(dynamic value) => OperationAuthorKindEnumTypeTransformer().decode(value);

  /// Returns a [List] containing instances of [OperationAuthorKindEnum]
  /// that were successfully decoded from the passed [JSON][json].
  static List<OperationAuthorKindEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <OperationAuthorKindEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = OperationAuthorKindEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [OperationAuthorKindEnum] to String,
/// and [decode] dynamic data back to [OperationAuthorKindEnum].
class OperationAuthorKindEnumTypeTransformer {
  factory OperationAuthorKindEnumTypeTransformer() => _instance ??= const OperationAuthorKindEnumTypeTransformer._();

  const OperationAuthorKindEnumTypeTransformer._();

  String encode(OperationAuthorKindEnum data) => data._value;

  /// Returns the instance of [OperationAuthorKindEnum] that was successfully decoded
  /// from the passed [data] value on success, null otherwise.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  OperationAuthorKindEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data is OperationAuthorKindEnum) {
      return data;
    }
    if (data != null) {
      switch (data) {
        case r'person': return OperationAuthorKindEnum.person;
        case r'agent': return OperationAuthorKindEnum.agent;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// The singleton instance of this transformer.
  static OperationAuthorKindEnumTypeTransformer? _instance;
}



enum OperationKindEnum {
  delta._(r'delta'),
  action._(r'action'),
  restore._(r'restore'),
  ;

  /// Instantiate a new enum with the provided value.
  const OperationKindEnum._(this._value);

  /// The underlying value of this enum member.
  final String _value;

  @override
  String toString() => _value;

  /// Encodes this enum as a value suitable for JSON.
  String toJson() => _value;

  /// Returns the instance of [OperationKindEnum] that was successfully decoded
  /// from the passed [value] on success, null otherwise.
  static OperationKindEnum? fromJson(dynamic value) => OperationKindEnumTypeTransformer().decode(value);

  /// Returns a [List] containing instances of [OperationKindEnum]
  /// that were successfully decoded from the passed [JSON][json].
  static List<OperationKindEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <OperationKindEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = OperationKindEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [OperationKindEnum] to String,
/// and [decode] dynamic data back to [OperationKindEnum].
class OperationKindEnumTypeTransformer {
  factory OperationKindEnumTypeTransformer() => _instance ??= const OperationKindEnumTypeTransformer._();

  const OperationKindEnumTypeTransformer._();

  String encode(OperationKindEnum data) => data._value;

  /// Returns the instance of [OperationKindEnum] that was successfully decoded
  /// from the passed [data] value on success, null otherwise.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  OperationKindEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data is OperationKindEnum) {
      return data;
    }
    if (data != null) {
      switch (data) {
        case r'delta': return OperationKindEnum.delta;
        case r'action': return OperationKindEnum.action;
        case r'restore': return OperationKindEnum.restore;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// The singleton instance of this transformer.
  static OperationKindEnumTypeTransformer? _instance;
}


