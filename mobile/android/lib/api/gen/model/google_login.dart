//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class GoogleLogin {
  /// Returns a new [GoogleLogin] instance.
  GoogleLogin({
    required this.credential,
  });

  String credential;

  @override
  bool operator ==(Object other) => identical(this, other) || other is GoogleLogin &&
    other.credential == credential;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (credential.hashCode);

  @override
  String toString() => 'GoogleLogin[credential=$credential]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'credential'] = this.credential;
    return json;
  }

  /// Returns a new [GoogleLogin] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static GoogleLogin? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'credential'), 'Required key "GoogleLogin[credential]" is missing from JSON.');
        assert(json[r'credential'] != null, 'Required key "GoogleLogin[credential]" has a null value in JSON.');
        return true;
      }());

      return GoogleLogin(
        credential: mapValueOfType<String>(json, r'credential')!,
      );
    }
    return null;
  }

  static List<GoogleLogin> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <GoogleLogin>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = GoogleLogin.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, GoogleLogin> mapFromJson(dynamic json) {
    final map = <String, GoogleLogin>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = GoogleLogin.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of GoogleLogin-objects as value to a dart map
  static Map<String, List<GoogleLogin>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<GoogleLogin>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = GoogleLogin.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'credential',
  };
}

