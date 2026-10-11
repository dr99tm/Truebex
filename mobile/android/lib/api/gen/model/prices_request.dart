//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PricesRequest {
  /// Returns a new [PricesRequest] instance.
  PricesRequest({
    this.items = const [],
    required this.region,
  });

  List<PriceItem> items;

  String region;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PricesRequest &&
    _deepEquality.equals(other.items, items) &&
    other.region == region;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (items.hashCode) +
    (region.hashCode);

  @override
  String toString() => 'PricesRequest[items=$items, region=$region]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'items'] = this.items;
      json[r'region'] = this.region;
    return json;
  }

  /// Returns a new [PricesRequest] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PricesRequest? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'items'), 'Required key "PricesRequest[items]" is missing from JSON.');
        assert(json[r'items'] != null, 'Required key "PricesRequest[items]" has a null value in JSON.');
        assert(json.containsKey(r'region'), 'Required key "PricesRequest[region]" is missing from JSON.');
        assert(json[r'region'] != null, 'Required key "PricesRequest[region]" has a null value in JSON.');
        return true;
      }());

      return PricesRequest(
        items: PriceItem.listFromJson(json[r'items']),
        region: mapValueOfType<String>(json, r'region')!,
      );
    }
    return null;
  }

  static List<PricesRequest> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PricesRequest>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PricesRequest.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PricesRequest> mapFromJson(dynamic json) {
    final map = <String, PricesRequest>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PricesRequest.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PricesRequest-objects as value to a dart map
  static Map<String, List<PricesRequest>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PricesRequest>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PricesRequest.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'items',
    'region',
  };
}

