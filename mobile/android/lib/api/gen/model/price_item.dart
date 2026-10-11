//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PriceItem {
  /// Returns a new [PriceItem] instance.
  PriceItem({
    this.qty,
    required this.sku,
    required this.supplierId,
    required this.variantId,
  });

  /// Minimum value: 1
  /// Maximum value: 100000
  int? qty;

  String sku;

  String supplierId;

  String variantId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PriceItem &&
    other.qty == qty &&
    other.sku == sku &&
    other.supplierId == supplierId &&
    other.variantId == variantId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (qty == null ? 0 : qty!.hashCode) +
    (sku.hashCode) +
    (supplierId.hashCode) +
    (variantId.hashCode);

  @override
  String toString() => 'PriceItem[qty=$qty, sku=$sku, supplierId=$supplierId, variantId=$variantId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.qty != null) {
      json[r'qty'] = this.qty;
    } else {
      json[r'qty'] = null;
    }
      json[r'sku'] = this.sku;
      json[r'supplier_id'] = this.supplierId;
      json[r'variant_id'] = this.variantId;
    return json;
  }

  /// Returns a new [PriceItem] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PriceItem? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'sku'), 'Required key "PriceItem[sku]" is missing from JSON.');
        assert(json[r'sku'] != null, 'Required key "PriceItem[sku]" has a null value in JSON.');
        assert(json.containsKey(r'supplier_id'), 'Required key "PriceItem[supplier_id]" is missing from JSON.');
        assert(json[r'supplier_id'] != null, 'Required key "PriceItem[supplier_id]" has a null value in JSON.');
        assert(json.containsKey(r'variant_id'), 'Required key "PriceItem[variant_id]" is missing from JSON.');
        assert(json[r'variant_id'] != null, 'Required key "PriceItem[variant_id]" has a null value in JSON.');
        return true;
      }());

      return PriceItem(
        qty: mapValueOfType<int>(json, r'qty'),
        sku: mapValueOfType<String>(json, r'sku')!,
        supplierId: mapValueOfType<String>(json, r'supplier_id')!,
        variantId: mapValueOfType<String>(json, r'variant_id')!,
      );
    }
    return null;
  }

  static List<PriceItem> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PriceItem>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PriceItem.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PriceItem> mapFromJson(dynamic json) {
    final map = <String, PriceItem>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PriceItem.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PriceItem-objects as value to a dart map
  static Map<String, List<PriceItem>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PriceItem>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PriceItem.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'sku',
    'supplier_id',
    'variant_id',
  };
}

