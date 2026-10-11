//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class SearchAnswer {
  /// Returns a new [SearchAnswer] instance.
  SearchAnswer({
    this.nextCursor,
    this.results = const [],
  });

  String? nextCursor;

  List<SearchHit> results;

  @override
  bool operator ==(Object other) => identical(this, other) || other is SearchAnswer &&
    other.nextCursor == nextCursor &&
    _deepEquality.equals(other.results, results);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (nextCursor == null ? 0 : nextCursor!.hashCode) +
    (results.hashCode);

  @override
  String toString() => 'SearchAnswer[nextCursor=$nextCursor, results=$results]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.nextCursor != null) {
      json[r'next_cursor'] = this.nextCursor;
    } else {
      json[r'next_cursor'] = null;
    }
      json[r'results'] = this.results;
    return json;
  }

  /// Returns a new [SearchAnswer] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static SearchAnswer? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'results'), 'Required key "SearchAnswer[results]" is missing from JSON.');
        assert(json[r'results'] != null, 'Required key "SearchAnswer[results]" has a null value in JSON.');
        return true;
      }());

      return SearchAnswer(
        nextCursor: mapValueOfType<String>(json, r'next_cursor'),
        results: SearchHit.listFromJson(json[r'results']),
      );
    }
    return null;
  }

  static List<SearchAnswer> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <SearchAnswer>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = SearchAnswer.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, SearchAnswer> mapFromJson(dynamic json) {
    final map = <String, SearchAnswer>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = SearchAnswer.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of SearchAnswer-objects as value to a dart map
  static Map<String, List<SearchAnswer>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<SearchAnswer>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = SearchAnswer.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'results',
  };
}

