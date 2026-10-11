//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PushResult {
  /// Returns a new [PushResult] instance.
  PushResult({
    this.more,
    required this.opId,
    this.reason,
    this.serverSeq,
    required this.status,
    this.winning = const [],
  });

  bool? more;

  String opId;

  String? reason;

  int? serverSeq;

  PushResultStatusEnum status;

  List<Operation>? winning;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PushResult &&
    other.more == more &&
    other.opId == opId &&
    other.reason == reason &&
    other.serverSeq == serverSeq &&
    other.status == status &&
    _deepEquality.equals(other.winning, winning);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (more == null ? 0 : more!.hashCode) +
    (opId.hashCode) +
    (reason == null ? 0 : reason!.hashCode) +
    (serverSeq == null ? 0 : serverSeq!.hashCode) +
    (status.hashCode) +
    (winning == null ? 0 : winning!.hashCode);

  @override
  String toString() => 'PushResult[more=$more, opId=$opId, reason=$reason, serverSeq=$serverSeq, status=$status, winning=$winning]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.more != null) {
      json[r'more'] = this.more;
    } else {
      json[r'more'] = null;
    }
      json[r'op_id'] = this.opId;
    if (this.reason != null) {
      json[r'reason'] = this.reason;
    } else {
      json[r'reason'] = null;
    }
    if (this.serverSeq != null) {
      json[r'server_seq'] = this.serverSeq;
    } else {
      json[r'server_seq'] = null;
    }
      json[r'status'] = this.status;
    if (this.winning != null) {
      json[r'winning'] = this.winning;
    } else {
      json[r'winning'] = null;
    }
    return json;
  }

  /// Returns a new [PushResult] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PushResult? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'op_id'), 'Required key "PushResult[op_id]" is missing from JSON.');
        assert(json[r'op_id'] != null, 'Required key "PushResult[op_id]" has a null value in JSON.');
        assert(json.containsKey(r'status'), 'Required key "PushResult[status]" is missing from JSON.');
        assert(json[r'status'] != null, 'Required key "PushResult[status]" has a null value in JSON.');
        return true;
      }());

      return PushResult(
        more: mapValueOfType<bool>(json, r'more'),
        opId: mapValueOfType<String>(json, r'op_id')!,
        reason: mapValueOfType<String>(json, r'reason'),
        serverSeq: mapValueOfType<int>(json, r'server_seq'),
        status: PushResultStatusEnum.fromJson(json[r'status'])!,
        winning: Operation.listFromJson(json[r'winning']),
      );
    }
    return null;
  }

  static List<PushResult> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PushResult>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PushResult.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PushResult> mapFromJson(dynamic json) {
    final map = <String, PushResult>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PushResult.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PushResult-objects as value to a dart map
  static Map<String, List<PushResult>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PushResult>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PushResult.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'op_id',
    'status',
  };
}


enum PushResultStatusEnum {
  accepted._(r'accepted'),
  duplicate._(r'duplicate'),
  rejected._(r'rejected'),
  notProcessed._(r'not_processed'),
  ;

  /// Instantiate a new enum with the provided value.
  const PushResultStatusEnum._(this._value);

  /// The underlying value of this enum member.
  final String _value;

  @override
  String toString() => _value;

  /// Encodes this enum as a value suitable for JSON.
  String toJson() => _value;

  /// Returns the instance of [PushResultStatusEnum] that was successfully decoded
  /// from the passed [value] on success, null otherwise.
  static PushResultStatusEnum? fromJson(dynamic value) => PushResultStatusEnumTypeTransformer().decode(value);

  /// Returns a [List] containing instances of [PushResultStatusEnum]
  /// that were successfully decoded from the passed [JSON][json].
  static List<PushResultStatusEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PushResultStatusEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PushResultStatusEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [PushResultStatusEnum] to String,
/// and [decode] dynamic data back to [PushResultStatusEnum].
class PushResultStatusEnumTypeTransformer {
  factory PushResultStatusEnumTypeTransformer() => _instance ??= const PushResultStatusEnumTypeTransformer._();

  const PushResultStatusEnumTypeTransformer._();

  String encode(PushResultStatusEnum data) => data._value;

  /// Returns the instance of [PushResultStatusEnum] that was successfully decoded
  /// from the passed [data] value on success, null otherwise.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  PushResultStatusEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data is PushResultStatusEnum) {
      return data;
    }
    if (data != null) {
      switch (data) {
        case r'accepted': return PushResultStatusEnum.accepted;
        case r'duplicate': return PushResultStatusEnum.duplicate;
        case r'rejected': return PushResultStatusEnum.rejected;
        case r'not_processed': return PushResultStatusEnum.notProcessed;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// The singleton instance of this transformer.
  static PushResultStatusEnumTypeTransformer? _instance;
}


