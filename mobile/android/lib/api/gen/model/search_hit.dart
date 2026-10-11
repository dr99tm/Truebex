//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class SearchHit {
  /// Returns a new [SearchHit] instance.
  SearchHit({
    required this.category,
    required this.name,
    required this.price,
    required this.productId,
    required this.supplierId,
    required this.variantId,
  });

  String? category;

  String name;

  Price? price;

  String productId;

  String supplierId;

  String? variantId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is SearchHit &&
    other.category == category &&
    other.name == name &&
    other.price == price &&
    other.productId == productId &&
    other.supplierId == supplierId &&
    other.variantId == variantId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (category == null ? 0 : category!.hashCode) +
    (name.hashCode) +
    (price == null ? 0 : price!.hashCode) +
    (productId.hashCode) +
    (supplierId.hashCode) +
    (variantId == null ? 0 : variantId!.hashCode);

  @override
  String toString() => 'SearchHit[category=$category, name=$name, price=$price, productId=$productId, supplierId=$supplierId, variantId=$variantId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.category != null) {
      json[r'category'] = this.category;
    } else {
      json[r'category'] = null;
    }
      json[r'name'] = this.name;
    if (this.price != null) {
      json[r'price'] = this.price;
    } else {
      json[r'price'] = null;
    }
      json[r'product_id'] = this.productId;
      json[r'supplier_id'] = this.supplierId;
    if (this.variantId != null) {
      json[r'variant_id'] = this.variantId;
    } else {
      json[r'variant_id'] = null;
    }
    return json;
  }

  /// Returns a new [SearchHit] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static SearchHit? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'category'), 'Required key "SearchHit[category]" is missing from JSON.');
        assert(json.containsKey(r'name'), 'Required key "SearchHit[name]" is missing from JSON.');
        assert(json[r'name'] != null, 'Required key "SearchHit[name]" has a null value in JSON.');
        assert(json.containsKey(r'price'), 'Required key "SearchHit[price]" is missing from JSON.');
        assert(json.containsKey(r'product_id'), 'Required key "SearchHit[product_id]" is missing from JSON.');
        assert(json[r'product_id'] != null, 'Required key "SearchHit[product_id]" has a null value in JSON.');
        assert(json.containsKey(r'supplier_id'), 'Required key "SearchHit[supplier_id]" is missing from JSON.');
        assert(json[r'supplier_id'] != null, 'Required key "SearchHit[supplier_id]" has a null value in JSON.');
        assert(json.containsKey(r'variant_id'), 'Required key "SearchHit[variant_id]" is missing from JSON.');
        return true;
      }());

      return SearchHit(
        category: mapValueOfType<String>(json, r'category'),
        name: mapValueOfType<String>(json, r'name')!,
        price: Price.fromJson(json[r'price']),
        productId: mapValueOfType<String>(json, r'product_id')!,
        supplierId: mapValueOfType<String>(json, r'supplier_id')!,
        variantId: mapValueOfType<String>(json, r'variant_id'),
      );
    }
    return null;
  }

  static List<SearchHit> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <SearchHit>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = SearchHit.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, SearchHit> mapFromJson(dynamic json) {
    final map = <String, SearchHit>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = SearchHit.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of SearchHit-objects as value to a dart map
  static Map<String, List<SearchHit>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<SearchHit>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = SearchHit.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'category',
    'name',
    'price',
    'product_id',
    'supplier_id',
    'variant_id',
  };
}

