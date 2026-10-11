//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PushAnswer {
  /// Returns a new [PushAnswer] instance.
  PushAnswer({
    required this.headSeq,
    this.results = const [],
  });

  int headSeq;

  List<PushResult> results;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PushAnswer &&
    other.headSeq == headSeq &&
    _deepEquality.equals(other.results, results);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (headSeq.hashCode) +
    (results.hashCode);

  @override
  String toString() => 'PushAnswer[headSeq=$headSeq, results=$results]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'head_seq'] = this.headSeq;
      json[r'results'] = this.results;
    return json;
  }

  /// Returns a new [PushAnswer] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PushAnswer? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'head_seq'), 'Required key "PushAnswer[head_seq]" is missing from JSON.');
        assert(json[r'head_seq'] != null, 'Required key "PushAnswer[head_seq]" has a null value in JSON.');
        assert(json.containsKey(r'results'), 'Required key "PushAnswer[results]" is missing from JSON.');
        assert(json[r'results'] != null, 'Required key "PushAnswer[results]" has a null value in JSON.');
        return true;
      }());

      return PushAnswer(
        headSeq: mapValueOfType<int>(json, r'head_seq')!,
        results: PushResult.listFromJson(json[r'results']),
      );
    }
    return null;
  }

  static List<PushAnswer> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PushAnswer>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PushAnswer.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PushAnswer> mapFromJson(dynamic json) {
    final map = <String, PushAnswer>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PushAnswer.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PushAnswer-objects as value to a dart map
  static Map<String, List<PushAnswer>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PushAnswer>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PushAnswer.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'head_seq',
    'results',
  };
}

