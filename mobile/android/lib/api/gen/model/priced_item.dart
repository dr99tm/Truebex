//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PricedItem {
  /// Returns a new [PricedItem] instance.
  PricedItem({
    required this.availability,
    required this.price,
    this.qty,
    required this.sku,
    this.status,
    this.substitutes = const [],
    required this.supplierId,
    required this.variantId,
  });

  Availability? availability;

  Price? price;

  int? qty;

  String sku;

  String? status;

  List<Object> substitutes;

  String supplierId;

  String variantId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PricedItem &&
    other.availability == availability &&
    other.price == price &&
    other.qty == qty &&
    other.sku == sku &&
    other.status == status &&
    _deepEquality.equals(other.substitutes, substitutes) &&
    other.supplierId == supplierId &&
    other.variantId == variantId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (availability == null ? 0 : availability!.hashCode) +
    (price == null ? 0 : price!.hashCode) +
    (qty == null ? 0 : qty!.hashCode) +
    (sku.hashCode) +
    (status == null ? 0 : status!.hashCode) +
    (substitutes.hashCode) +
    (supplierId.hashCode) +
    (variantId.hashCode);

  @override
  String toString() => 'PricedItem[availability=$availability, price=$price, qty=$qty, sku=$sku, status=$status, substitutes=$substitutes, supplierId=$supplierId, variantId=$variantId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.availability != null) {
      json[r'availability'] = this.availability;
    } else {
      json[r'availability'] = null;
    }
    if (this.price != null) {
      json[r'price'] = this.price;
    } else {
      json[r'price'] = null;
    }
    if (this.qty != null) {
      json[r'qty'] = this.qty;
    } else {
      json[r'qty'] = null;
    }
      json[r'sku'] = this.sku;
    if (this.status != null) {
      json[r'status'] = this.status;
    } else {
      json[r'status'] = null;
    }
      json[r'substitutes'] = this.substitutes;
      json[r'supplier_id'] = this.supplierId;
      json[r'variant_id'] = this.variantId;
    return json;
  }

  /// Returns a new [PricedItem] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PricedItem? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'availability'), 'Required key "PricedItem[availability]" is missing from JSON.');
        assert(json.containsKey(r'price'), 'Required key "PricedItem[price]" is missing from JSON.');
        assert(json.containsKey(r'sku'), 'Required key "PricedItem[sku]" is missing from JSON.');
        assert(json[r'sku'] != null, 'Required key "PricedItem[sku]" has a null value in JSON.');
        assert(json.containsKey(r'substitutes'), 'Required key "PricedItem[substitutes]" is missing from JSON.');
        assert(json[r'substitutes'] != null, 'Required key "PricedItem[substitutes]" has a null value in JSON.');
        assert(json.containsKey(r'supplier_id'), 'Required key "PricedItem[supplier_id]" is missing from JSON.');
        assert(json[r'supplier_id'] != null, 'Required key "PricedItem[supplier_id]" has a null value in JSON.');
        assert(json.containsKey(r'variant_id'), 'Required key "PricedItem[variant_id]" is missing from JSON.');
        assert(json[r'variant_id'] != null, 'Required key "PricedItem[variant_id]" has a null value in JSON.');
        return true;
      }());

      return PricedItem(
        availability: Availability.fromJson(json[r'availability']),
        price: Price.fromJson(json[r'price']),
        qty: mapValueOfType<int>(json, r'qty'),
        sku: mapValueOfType<String>(json, r'sku')!,
        status: mapValueOfType<String>(json, r'status'),
        substitutes: json[r'substitutes'] is Iterable
            ? (json[r'substitutes'] as Iterable).cast<Object>().toList(growable: false)
            : const [],
        supplierId: mapValueOfType<String>(json, r'supplier_id')!,
        variantId: mapValueOfType<String>(json, r'variant_id')!,
      );
    }
    return null;
  }

  static List<PricedItem> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PricedItem>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PricedItem.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PricedItem> mapFromJson(dynamic json) {
    final map = <String, PricedItem>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PricedItem.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PricedItem-objects as value to a dart map
  static Map<String, List<PricedItem>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PricedItem>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PricedItem.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'availability',
    'price',
    'sku',
    'substitutes',
    'supplier_id',
    'variant_id',
  };
}

