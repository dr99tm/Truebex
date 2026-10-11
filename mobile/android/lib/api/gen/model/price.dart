//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class Price {
  /// Returns a new [Price] instance.
  Price({
    required this.amount,
    required this.at,
    required this.currency,
    required this.exponent,
    required this.includesTax,
    required this.region,
    required this.taxRateBp,
  });

  int amount;

  String? at;

  String currency;

  int exponent;

  bool includesTax;

  String region;

  int taxRateBp;

  @override
  bool operator ==(Object other) => identical(this, other) || other is Price &&
    other.amount == amount &&
    other.at == at &&
    other.currency == currency &&
    other.exponent == exponent &&
    other.includesTax == includesTax &&
    other.region == region &&
    other.taxRateBp == taxRateBp;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (amount.hashCode) +
    (at == null ? 0 : at!.hashCode) +
    (currency.hashCode) +
    (exponent.hashCode) +
    (includesTax.hashCode) +
    (region.hashCode) +
    (taxRateBp.hashCode);

  @override
  String toString() => 'Price[amount=$amount, at=$at, currency=$currency, exponent=$exponent, includesTax=$includesTax, region=$region, taxRateBp=$taxRateBp]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'amount'] = this.amount;
    if (this.at != null) {
      json[r'at'] = this.at;
    } else {
      json[r'at'] = null;
    }
      json[r'currency'] = this.currency;
      json[r'exponent'] = this.exponent;
      json[r'includes_tax'] = this.includesTax;
      json[r'region'] = this.region;
      json[r'tax_rate_bp'] = this.taxRateBp;
    return json;
  }

  /// Returns a new [Price] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static Price? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'amount'), 'Required key "Price[amount]" is missing from JSON.');
        assert(json[r'amount'] != null, 'Required key "Price[amount]" has a null value in JSON.');
        assert(json.containsKey(r'at'), 'Required key "Price[at]" is missing from JSON.');
        assert(json.containsKey(r'currency'), 'Required key "Price[currency]" is missing from JSON.');
        assert(json[r'currency'] != null, 'Required key "Price[currency]" has a null value in JSON.');
        assert(json.containsKey(r'exponent'), 'Required key "Price[exponent]" is missing from JSON.');
        assert(json[r'exponent'] != null, 'Required key "Price[exponent]" has a null value in JSON.');
        assert(json.containsKey(r'includes_tax'), 'Required key "Price[includes_tax]" is missing from JSON.');
        assert(json[r'includes_tax'] != null, 'Required key "Price[includes_tax]" has a null value in JSON.');
        assert(json.containsKey(r'region'), 'Required key "Price[region]" is missing from JSON.');
        assert(json[r'region'] != null, 'Required key "Price[region]" has a null value in JSON.');
        assert(json.containsKey(r'tax_rate_bp'), 'Required key "Price[tax_rate_bp]" is missing from JSON.');
        assert(json[r'tax_rate_bp'] != null, 'Required key "Price[tax_rate_bp]" has a null value in JSON.');
        return true;
      }());

      return Price(
        amount: mapValueOfType<int>(json, r'amount')!,
        at: mapValueOfType<String>(json, r'at'),
        currency: mapValueOfType<String>(json, r'currency')!,
        exponent: mapValueOfType<int>(json, r'exponent')!,
        includesTax: mapValueOfType<bool>(json, r'includes_tax')!,
        region: mapValueOfType<String>(json, r'region')!,
        taxRateBp: mapValueOfType<int>(json, r'tax_rate_bp')!,
      );
    }
    return null;
  }

  static List<Price> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <Price>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = Price.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, Price> mapFromJson(dynamic json) {
    final map = <String, Price>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = Price.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of Price-objects as value to a dart map
  static Map<String, List<Price>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<Price>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = Price.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'amount',
    'at',
    'currency',
    'exponent',
    'includes_tax',
    'region',
    'tax_rate_bp',
  };
}

