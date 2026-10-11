//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PricesAnswer {
  /// Returns a new [PricesAnswer] instance.
  PricesAnswer({
    this.items = const [],
  });

  List<PricedItem> items;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PricesAnswer &&
    _deepEquality.equals(other.items, items);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (items.hashCode);

  @override
  String toString() => 'PricesAnswer[items=$items]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'items'] = this.items;
    return json;
  }

  /// Returns a new [PricesAnswer] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PricesAnswer? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'items'), 'Required key "PricesAnswer[items]" is missing from JSON.');
        assert(json[r'items'] != null, 'Required key "PricesAnswer[items]" has a null value in JSON.');
        return true;
      }());

      return PricesAnswer(
        items: PricedItem.listFromJson(json[r'items']),
      );
    }
    return null;
  }

  static List<PricesAnswer> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PricesAnswer>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PricesAnswer.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PricesAnswer> mapFromJson(dynamic json) {
    final map = <String, PricesAnswer>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PricesAnswer.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PricesAnswer-objects as value to a dart map
  static Map<String, List<PricesAnswer>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PricesAnswer>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PricesAnswer.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'items',
  };
}

