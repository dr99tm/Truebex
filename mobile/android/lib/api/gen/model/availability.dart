//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class Availability {
  /// Returns a new [Availability] instance.
  Availability({
    required this.state,
  });

  String state;

  @override
  bool operator ==(Object other) => identical(this, other) || other is Availability &&
    other.state == state;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (state.hashCode);

  @override
  String toString() => 'Availability[state=$state]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'state'] = this.state;
    return json;
  }

  /// Returns a new [Availability] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static Availability? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'state'), 'Required key "Availability[state]" is missing from JSON.');
        assert(json[r'state'] != null, 'Required key "Availability[state]" has a null value in JSON.');
        return true;
      }());

      return Availability(
        state: mapValueOfType<String>(json, r'state')!,
      );
    }
    return null;
  }

  static List<Availability> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <Availability>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = Availability.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, Availability> mapFromJson(dynamic json) {
    final map = <String, Availability>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = Availability.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of Availability-objects as value to a dart map
  static Map<String, List<Availability>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<Availability>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = Availability.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'state',
  };
}

