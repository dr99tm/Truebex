//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class SnapshotFiles {
  /// Returns a new [SnapshotFiles] instance.
  SnapshotFiles({
    this.digest,
    required this.tbxp,
    required this.tbxpack,
  });

  SnapshotFile? digest;

  SnapshotFile? tbxp;

  SnapshotFile? tbxpack;

  @override
  bool operator ==(Object other) => identical(this, other) || other is SnapshotFiles &&
    other.digest == digest &&
    other.tbxp == tbxp &&
    other.tbxpack == tbxpack;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (digest == null ? 0 : digest!.hashCode) +
    (tbxp == null ? 0 : tbxp!.hashCode) +
    (tbxpack == null ? 0 : tbxpack!.hashCode);

  @override
  String toString() => 'SnapshotFiles[digest=$digest, tbxp=$tbxp, tbxpack=$tbxpack]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.digest != null) {
      json[r'digest'] = this.digest;
    } else {
      json[r'digest'] = null;
    }
    if (this.tbxp != null) {
      json[r'tbxp'] = this.tbxp;
    } else {
      json[r'tbxp'] = null;
    }
    if (this.tbxpack != null) {
      json[r'tbxpack'] = this.tbxpack;
    } else {
      json[r'tbxpack'] = null;
    }
    return json;
  }

  /// Returns a new [SnapshotFiles] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static SnapshotFiles? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'tbxp'), 'Required key "SnapshotFiles[tbxp]" is missing from JSON.');
        assert(json.containsKey(r'tbxpack'), 'Required key "SnapshotFiles[tbxpack]" is missing from JSON.');
        return true;
      }());

      return SnapshotFiles(
        digest: SnapshotFile.fromJson(json[r'digest']),
        tbxp: SnapshotFile.fromJson(json[r'tbxp']),
        tbxpack: SnapshotFile.fromJson(json[r'tbxpack']),
      );
    }
    return null;
  }

  static List<SnapshotFiles> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <SnapshotFiles>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = SnapshotFiles.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, SnapshotFiles> mapFromJson(dynamic json) {
    final map = <String, SnapshotFiles>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = SnapshotFiles.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of SnapshotFiles-objects as value to a dart map
  static Map<String, List<SnapshotFiles>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<SnapshotFiles>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = SnapshotFiles.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'tbxp',
    'tbxpack',
  };
}

