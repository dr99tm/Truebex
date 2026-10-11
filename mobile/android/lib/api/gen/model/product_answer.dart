//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class ProductAnswer {
  /// Returns a new [ProductAnswer] instance.
  ProductAnswer({
    required this.category,
    required this.name,
    required this.productId,
    required this.sku,
    required this.supplierId,
    this.variants = const [],
  });

  String? category;

  String name;

  String productId;

  String sku;

  String supplierId;

  List<ProductVariant> variants;

  @override
  bool operator ==(Object other) => identical(this, other) || other is ProductAnswer &&
    other.category == category &&
    other.name == name &&
    other.productId == productId &&
    other.sku == sku &&
    other.supplierId == supplierId &&
    _deepEquality.equals(other.variants, variants);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (category == null ? 0 : category!.hashCode) +
    (name.hashCode) +
    (productId.hashCode) +
    (sku.hashCode) +
    (supplierId.hashCode) +
    (variants.hashCode);

  @override
  String toString() => 'ProductAnswer[category=$category, name=$name, productId=$productId, sku=$sku, supplierId=$supplierId, variants=$variants]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.category != null) {
      json[r'category'] = this.category;
    } else {
      json[r'category'] = null;
    }
      json[r'name'] = this.name;
      json[r'product_id'] = this.productId;
      json[r'sku'] = this.sku;
      json[r'supplier_id'] = this.supplierId;
      json[r'variants'] = this.variants;
    return json;
  }

  /// Returns a new [ProductAnswer] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static ProductAnswer? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'category'), 'Required key "ProductAnswer[category]" is missing from JSON.');
        assert(json.containsKey(r'name'), 'Required key "ProductAnswer[name]" is missing from JSON.');
        assert(json[r'name'] != null, 'Required key "ProductAnswer[name]" has a null value in JSON.');
        assert(json.containsKey(r'product_id'), 'Required key "ProductAnswer[product_id]" is missing from JSON.');
        assert(json[r'product_id'] != null, 'Required key "ProductAnswer[product_id]" has a null value in JSON.');
        assert(json.containsKey(r'sku'), 'Required key "ProductAnswer[sku]" is missing from JSON.');
        assert(json[r'sku'] != null, 'Required key "ProductAnswer[sku]" has a null value in JSON.');
        assert(json.containsKey(r'supplier_id'), 'Required key "ProductAnswer[supplier_id]" is missing from JSON.');
        assert(json[r'supplier_id'] != null, 'Required key "ProductAnswer[supplier_id]" has a null value in JSON.');
        assert(json.containsKey(r'variants'), 'Required key "ProductAnswer[variants]" is missing from JSON.');
        assert(json[r'variants'] != null, 'Required key "ProductAnswer[variants]" has a null value in JSON.');
        return true;
      }());

      return ProductAnswer(
        category: mapValueOfType<String>(json, r'category'),
        name: mapValueOfType<String>(json, r'name')!,
        productId: mapValueOfType<String>(json, r'product_id')!,
        sku: mapValueOfType<String>(json, r'sku')!,
        supplierId: mapValueOfType<String>(json, r'supplier_id')!,
        variants: ProductVariant.listFromJson(json[r'variants']),
      );
    }
    return null;
  }

  static List<ProductAnswer> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <ProductAnswer>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = ProductAnswer.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, ProductAnswer> mapFromJson(dynamic json) {
    final map = <String, ProductAnswer>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = ProductAnswer.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of ProductAnswer-objects as value to a dart map
  static Map<String, List<ProductAnswer>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<ProductAnswer>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = ProductAnswer.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'category',
    'name',
    'product_id',
    'sku',
    'supplier_id',
    'variants',
  };
}

