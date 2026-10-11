//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PresenceView {
  /// Returns a new [PresenceView] instance.
  PresenceView({
    this.eyeMm = const [],
    this.storey,
    this.yawDeg,
  });

  List<num>? eyeMm;

  String? storey;

  num? yawDeg;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PresenceView &&
    _deepEquality.equals(other.eyeMm, eyeMm) &&
    other.storey == storey &&
    other.yawDeg == yawDeg;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (eyeMm == null ? 0 : eyeMm!.hashCode) +
    (storey == null ? 0 : storey!.hashCode) +
    (yawDeg == null ? 0 : yawDeg!.hashCode);

  @override
  String toString() => 'PresenceView[eyeMm=$eyeMm, storey=$storey, yawDeg=$yawDeg]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.eyeMm != null) {
      json[r'eye_mm'] = this.eyeMm;
    } else {
      json[r'eye_mm'] = null;
    }
    if (this.storey != null) {
      json[r'storey'] = this.storey;
    } else {
      json[r'storey'] = null;
    }
    if (this.yawDeg != null) {
      json[r'yaw_deg'] = this.yawDeg;
    } else {
      json[r'yaw_deg'] = null;
    }
    return json;
  }

  /// Returns a new [PresenceView] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PresenceView? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        return true;
      }());

      return PresenceView(
        eyeMm: json[r'eye_mm'] is Iterable
            ? (json[r'eye_mm'] as Iterable).cast<num>().toList(growable: false)
            : const [],
        storey: mapValueOfType<String>(json, r'storey'),
        yawDeg: json[r'yaw_deg'] == null
            ? null
            : num.parse('${json[r'yaw_deg']}'),
      );
    }
    return null;
  }

  static List<PresenceView> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PresenceView>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PresenceView.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PresenceView> mapFromJson(dynamic json) {
    final map = <String, PresenceView>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PresenceView.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PresenceView-objects as value to a dart map
  static Map<String, List<PresenceView>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PresenceView>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PresenceView.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
  };
}

