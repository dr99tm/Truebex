//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class ProjectQuota {
  /// Returns a new [ProjectQuota] instance.
  ProjectQuota({
    required this.bytes,
    required this.bytesUsed,
  });

  int? bytes;

  int bytesUsed;

  @override
  bool operator ==(Object other) => identical(this, other) || other is ProjectQuota &&
    other.bytes == bytes &&
    other.bytesUsed == bytesUsed;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (bytes == null ? 0 : bytes!.hashCode) +
    (bytesUsed.hashCode);

  @override
  String toString() => 'ProjectQuota[bytes=$bytes, bytesUsed=$bytesUsed]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.bytes != null) {
      json[r'bytes'] = this.bytes;
    } else {
      json[r'bytes'] = null;
    }
      json[r'bytes_used'] = this.bytesUsed;
    return json;
  }

  /// Returns a new [ProjectQuota] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static ProjectQuota? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'bytes'), 'Required key "ProjectQuota[bytes]" is missing from JSON.');
        assert(json.containsKey(r'bytes_used'), 'Required key "ProjectQuota[bytes_used]" is missing from JSON.');
        assert(json[r'bytes_used'] != null, 'Required key "ProjectQuota[bytes_used]" has a null value in JSON.');
        return true;
      }());

      return ProjectQuota(
        bytes: mapValueOfType<int>(json, r'bytes'),
        bytesUsed: mapValueOfType<int>(json, r'bytes_used')!,
      );
    }
    return null;
  }

  static List<ProjectQuota> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <ProjectQuota>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = ProjectQuota.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, ProjectQuota> mapFromJson(dynamic json) {
    final map = <String, ProjectQuota>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = ProjectQuota.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of ProjectQuota-objects as value to a dart map
  static Map<String, List<ProjectQuota>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<ProjectQuota>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = ProjectQuota.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'bytes',
    'bytes_used',
  };
}

