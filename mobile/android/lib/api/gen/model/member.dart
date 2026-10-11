//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class Member {
  /// Returns a new [Member] instance.
  Member({
    required this.acceptedAt,
    required this.authorId,
    required this.email,
    required this.inviteId,
    required this.invitedAt,
    required this.name,
    required this.role,
    required this.state,
    required this.userId,
  });

  String? acceptedAt;

  String? authorId;

  String email;

  String? inviteId;

  String? invitedAt;

  String? name;

  String role;

  MemberStateEnum state;

  int? userId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is Member &&
    other.acceptedAt == acceptedAt &&
    other.authorId == authorId &&
    other.email == email &&
    other.inviteId == inviteId &&
    other.invitedAt == invitedAt &&
    other.name == name &&
    other.role == role &&
    other.state == state &&
    other.userId == userId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (acceptedAt == null ? 0 : acceptedAt!.hashCode) +
    (authorId == null ? 0 : authorId!.hashCode) +
    (email.hashCode) +
    (inviteId == null ? 0 : inviteId!.hashCode) +
    (invitedAt == null ? 0 : invitedAt!.hashCode) +
    (name == null ? 0 : name!.hashCode) +
    (role.hashCode) +
    (state.hashCode) +
    (userId == null ? 0 : userId!.hashCode);

  @override
  String toString() => 'Member[acceptedAt=$acceptedAt, authorId=$authorId, email=$email, inviteId=$inviteId, invitedAt=$invitedAt, name=$name, role=$role, state=$state, userId=$userId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.acceptedAt != null) {
      json[r'accepted_at'] = this.acceptedAt;
    } else {
      json[r'accepted_at'] = null;
    }
    if (this.authorId != null) {
      json[r'author_id'] = this.authorId;
    } else {
      json[r'author_id'] = null;
    }
      json[r'email'] = this.email;
    if (this.inviteId != null) {
      json[r'invite_id'] = this.inviteId;
    } else {
      json[r'invite_id'] = null;
    }
    if (this.invitedAt != null) {
      json[r'invited_at'] = this.invitedAt;
    } else {
      json[r'invited_at'] = null;
    }
    if (this.name != null) {
      json[r'name'] = this.name;
    } else {
      json[r'name'] = null;
    }
      json[r'role'] = this.role;
      json[r'state'] = this.state;
    if (this.userId != null) {
      json[r'user_id'] = this.userId;
    } else {
      json[r'user_id'] = null;
    }
    return json;
  }

  /// Returns a new [Member] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static Member? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'accepted_at'), 'Required key "Member[accepted_at]" is missing from JSON.');
        assert(json.containsKey(r'author_id'), 'Required key "Member[author_id]" is missing from JSON.');
        assert(json.containsKey(r'email'), 'Required key "Member[email]" is missing from JSON.');
        assert(json[r'email'] != null, 'Required key "Member[email]" has a null value in JSON.');
        assert(json.containsKey(r'invite_id'), 'Required key "Member[invite_id]" is missing from JSON.');
        assert(json.containsKey(r'invited_at'), 'Required key "Member[invited_at]" is missing from JSON.');
        assert(json.containsKey(r'name'), 'Required key "Member[name]" is missing from JSON.');
        assert(json.containsKey(r'role'), 'Required key "Member[role]" is missing from JSON.');
        assert(json[r'role'] != null, 'Required key "Member[role]" has a null value in JSON.');
        assert(json.containsKey(r'state'), 'Required key "Member[state]" is missing from JSON.');
        assert(json[r'state'] != null, 'Required key "Member[state]" has a null value in JSON.');
        assert(json.containsKey(r'user_id'), 'Required key "Member[user_id]" is missing from JSON.');
        return true;
      }());

      return Member(
        acceptedAt: mapValueOfType<String>(json, r'accepted_at'),
        authorId: mapValueOfType<String>(json, r'author_id'),
        email: mapValueOfType<String>(json, r'email')!,
        inviteId: mapValueOfType<String>(json, r'invite_id'),
        invitedAt: mapValueOfType<String>(json, r'invited_at'),
        name: mapValueOfType<String>(json, r'name'),
        role: mapValueOfType<String>(json, r'role')!,
        state: MemberStateEnum.fromJson(json[r'state'])!,
        userId: mapValueOfType<int>(json, r'user_id'),
      );
    }
    return null;
  }

  static List<Member> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <Member>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = Member.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, Member> mapFromJson(dynamic json) {
    final map = <String, Member>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = Member.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of Member-objects as value to a dart map
  static Map<String, List<Member>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<Member>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = Member.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'accepted_at',
    'author_id',
    'email',
    'invite_id',
    'invited_at',
    'name',
    'role',
    'state',
    'user_id',
  };
}


enum MemberStateEnum {
  active._(r'active'),
  invited._(r'invited'),
  ;

  /// Instantiate a new enum with the provided value.
  const MemberStateEnum._(this._value);

  /// The underlying value of this enum member.
  final String _value;

  @override
  String toString() => _value;

  /// Encodes this enum as a value suitable for JSON.
  String toJson() => _value;

  /// Returns the instance of [MemberStateEnum] that was successfully decoded
  /// from the passed [value] on success, null otherwise.
  static MemberStateEnum? fromJson(dynamic value) => MemberStateEnumTypeTransformer().decode(value);

  /// Returns a [List] containing instances of [MemberStateEnum]
  /// that were successfully decoded from the passed [JSON][json].
  static List<MemberStateEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <MemberStateEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = MemberStateEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [MemberStateEnum] to String,
/// and [decode] dynamic data back to [MemberStateEnum].
class MemberStateEnumTypeTransformer {
  factory MemberStateEnumTypeTransformer() => _instance ??= const MemberStateEnumTypeTransformer._();

  const MemberStateEnumTypeTransformer._();

  String encode(MemberStateEnum data) => data._value;

  /// Returns the instance of [MemberStateEnum] that was successfully decoded
  /// from the passed [data] value on success, null otherwise.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  MemberStateEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data is MemberStateEnum) {
      return data;
    }
    if (data != null) {
      switch (data) {
        case r'active': return MemberStateEnum.active;
        case r'invited': return MemberStateEnum.invited;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// The singleton instance of this transformer.
  static MemberStateEnumTypeTransformer? _instance;
}


