//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class UserLogin {
  /// Returns a new [UserLogin] instance.
  UserLogin({
    this.breakGlassCode,
    required this.email,
    required this.password,
  });

  String? breakGlassCode;

  String email;

  String password;

  @override
  bool operator ==(Object other) => identical(this, other) || other is UserLogin &&
    other.breakGlassCode == breakGlassCode &&
    other.email == email &&
    other.password == password;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (breakGlassCode == null ? 0 : breakGlassCode!.hashCode) +
    (email.hashCode) +
    (password.hashCode);

  @override
  String toString() => 'UserLogin[breakGlassCode=$breakGlassCode, email=$email, password=$password]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.breakGlassCode != null) {
      json[r'break_glass_code'] = this.breakGlassCode;
    } else {
      json[r'break_glass_code'] = null;
    }
      json[r'email'] = this.email;
      json[r'password'] = this.password;
    return json;
  }

  /// Returns a new [UserLogin] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static UserLogin? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'email'), 'Required key "UserLogin[email]" is missing from JSON.');
        assert(json[r'email'] != null, 'Required key "UserLogin[email]" has a null value in JSON.');
        assert(json.containsKey(r'password'), 'Required key "UserLogin[password]" is missing from JSON.');
        assert(json[r'password'] != null, 'Required key "UserLogin[password]" has a null value in JSON.');
        return true;
      }());

      return UserLogin(
        breakGlassCode: mapValueOfType<String>(json, r'break_glass_code'),
        email: mapValueOfType<String>(json, r'email')!,
        password: mapValueOfType<String>(json, r'password')!,
      );
    }
    return null;
  }

  static List<UserLogin> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <UserLogin>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = UserLogin.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, UserLogin> mapFromJson(dynamic json) {
    final map = <String, UserLogin>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = UserLogin.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of UserLogin-objects as value to a dart map
  static Map<String, List<UserLogin>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<UserLogin>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = UserLogin.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'email',
    'password',
  };
}

