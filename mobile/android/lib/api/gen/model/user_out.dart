//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class UserOut {
  /// Returns a new [UserOut] instance.
  UserOut({
    this.authorId,
    this.avatarUrl,
    required this.createdAt,
    required this.email,
    this.googleLinked = false,
    this.hasPassword = true,
    required this.id,
    this.isAdmin = false,
    this.name,
    required this.plan,
  });

  String? authorId;

  String? avatarUrl;

  DateTime createdAt;

  String email;

  bool googleLinked;

  bool hasPassword;

  int id;

  bool isAdmin;

  String? name;

  String plan;

  @override
  bool operator ==(Object other) => identical(this, other) || other is UserOut &&
    other.authorId == authorId &&
    other.avatarUrl == avatarUrl &&
    other.createdAt == createdAt &&
    other.email == email &&
    other.googleLinked == googleLinked &&
    other.hasPassword == hasPassword &&
    other.id == id &&
    other.isAdmin == isAdmin &&
    other.name == name &&
    other.plan == plan;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (authorId == null ? 0 : authorId!.hashCode) +
    (avatarUrl == null ? 0 : avatarUrl!.hashCode) +
    (createdAt.hashCode) +
    (email.hashCode) +
    (googleLinked.hashCode) +
    (hasPassword.hashCode) +
    (id.hashCode) +
    (isAdmin.hashCode) +
    (name == null ? 0 : name!.hashCode) +
    (plan.hashCode);

  @override
  String toString() => 'UserOut[authorId=$authorId, avatarUrl=$avatarUrl, createdAt=$createdAt, email=$email, googleLinked=$googleLinked, hasPassword=$hasPassword, id=$id, isAdmin=$isAdmin, name=$name, plan=$plan]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.authorId != null) {
      json[r'author_id'] = this.authorId;
    } else {
      json[r'author_id'] = null;
    }
    if (this.avatarUrl != null) {
      json[r'avatar_url'] = this.avatarUrl;
    } else {
      json[r'avatar_url'] = null;
    }
      json[r'created_at'] = this.createdAt.toUtc().toIso8601String();
      json[r'email'] = this.email;
      json[r'google_linked'] = this.googleLinked;
      json[r'has_password'] = this.hasPassword;
      json[r'id'] = this.id;
      json[r'is_admin'] = this.isAdmin;
    if (this.name != null) {
      json[r'name'] = this.name;
    } else {
      json[r'name'] = null;
    }
      json[r'plan'] = this.plan;
    return json;
  }

  /// Returns a new [UserOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static UserOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'created_at'), 'Required key "UserOut[created_at]" is missing from JSON.');
        assert(json[r'created_at'] != null, 'Required key "UserOut[created_at]" has a null value in JSON.');
        assert(json.containsKey(r'email'), 'Required key "UserOut[email]" is missing from JSON.');
        assert(json[r'email'] != null, 'Required key "UserOut[email]" has a null value in JSON.');
        assert(json.containsKey(r'id'), 'Required key "UserOut[id]" is missing from JSON.');
        assert(json[r'id'] != null, 'Required key "UserOut[id]" has a null value in JSON.');
        assert(json.containsKey(r'plan'), 'Required key "UserOut[plan]" is missing from JSON.');
        assert(json[r'plan'] != null, 'Required key "UserOut[plan]" has a null value in JSON.');
        return true;
      }());

      return UserOut(
        authorId: mapValueOfType<String>(json, r'author_id'),
        avatarUrl: mapValueOfType<String>(json, r'avatar_url'),
        createdAt: mapDateTime(json, r'created_at', r'')!,
        email: mapValueOfType<String>(json, r'email')!,
        googleLinked: mapValueOfType<bool>(json, r'google_linked') ?? false,
        hasPassword: mapValueOfType<bool>(json, r'has_password') ?? true,
        id: mapValueOfType<int>(json, r'id')!,
        isAdmin: mapValueOfType<bool>(json, r'is_admin') ?? false,
        name: mapValueOfType<String>(json, r'name'),
        plan: mapValueOfType<String>(json, r'plan')!,
      );
    }
    return null;
  }

  static List<UserOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <UserOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = UserOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, UserOut> mapFromJson(dynamic json) {
    final map = <String, UserOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = UserOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of UserOut-objects as value to a dart map
  static Map<String, List<UserOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<UserOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = UserOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'created_at',
    'email',
    'id',
    'plan',
  };
}

