//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PresenceAnswer {
  /// Returns a new [PresenceAnswer] instance.
  PresenceAnswer({
    this.others = const [],
    required this.ttlS,
  });

  List<Presence> others;

  int ttlS;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PresenceAnswer &&
    _deepEquality.equals(other.others, others) &&
    other.ttlS == ttlS;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (others.hashCode) +
    (ttlS.hashCode);

  @override
  String toString() => 'PresenceAnswer[others=$others, ttlS=$ttlS]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'others'] = this.others;
      json[r'ttl_s'] = this.ttlS;
    return json;
  }

  /// Returns a new [PresenceAnswer] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PresenceAnswer? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'others'), 'Required key "PresenceAnswer[others]" is missing from JSON.');
        assert(json[r'others'] != null, 'Required key "PresenceAnswer[others]" has a null value in JSON.');
        assert(json.containsKey(r'ttl_s'), 'Required key "PresenceAnswer[ttl_s]" is missing from JSON.');
        assert(json[r'ttl_s'] != null, 'Required key "PresenceAnswer[ttl_s]" has a null value in JSON.');
        return true;
      }());

      return PresenceAnswer(
        others: Presence.listFromJson(json[r'others']),
        ttlS: mapValueOfType<int>(json, r'ttl_s')!,
      );
    }
    return null;
  }

  static List<PresenceAnswer> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PresenceAnswer>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PresenceAnswer.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PresenceAnswer> mapFromJson(dynamic json) {
    final map = <String, PresenceAnswer>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PresenceAnswer.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PresenceAnswer-objects as value to a dart map
  static Map<String, List<PresenceAnswer>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PresenceAnswer>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PresenceAnswer.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'others',
    'ttl_s',
  };
}

