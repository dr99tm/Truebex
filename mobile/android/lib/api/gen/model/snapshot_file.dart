//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class SnapshotFile {
  /// Returns a new [SnapshotFile] instance.
  SnapshotFile({
    required this.bytes,
    required this.sha256,
    required this.url,
    required this.urlExpiresAt,
  });

  int? bytes;

  String sha256;

  String url;

  String urlExpiresAt;

  @override
  bool operator ==(Object other) => identical(this, other) || other is SnapshotFile &&
    other.bytes == bytes &&
    other.sha256 == sha256 &&
    other.url == url &&
    other.urlExpiresAt == urlExpiresAt;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (bytes == null ? 0 : bytes!.hashCode) +
    (sha256.hashCode) +
    (url.hashCode) +
    (urlExpiresAt.hashCode);

  @override
  String toString() => 'SnapshotFile[bytes=$bytes, sha256=$sha256, url=$url, urlExpiresAt=$urlExpiresAt]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.bytes != null) {
      json[r'bytes'] = this.bytes;
    } else {
      json[r'bytes'] = null;
    }
      json[r'sha256'] = this.sha256;
      json[r'url'] = this.url;
      json[r'url_expires_at'] = this.urlExpiresAt;
    return json;
  }

  /// Returns a new [SnapshotFile] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static SnapshotFile? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'bytes'), 'Required key "SnapshotFile[bytes]" is missing from JSON.');
        assert(json.containsKey(r'sha256'), 'Required key "SnapshotFile[sha256]" is missing from JSON.');
        assert(json[r'sha256'] != null, 'Required key "SnapshotFile[sha256]" has a null value in JSON.');
        assert(json.containsKey(r'url'), 'Required key "SnapshotFile[url]" is missing from JSON.');
        assert(json[r'url'] != null, 'Required key "SnapshotFile[url]" has a null value in JSON.');
        assert(json.containsKey(r'url_expires_at'), 'Required key "SnapshotFile[url_expires_at]" is missing from JSON.');
        assert(json[r'url_expires_at'] != null, 'Required key "SnapshotFile[url_expires_at]" has a null value in JSON.');
        return true;
      }());

      return SnapshotFile(
        bytes: mapValueOfType<int>(json, r'bytes'),
        sha256: mapValueOfType<String>(json, r'sha256')!,
        url: mapValueOfType<String>(json, r'url')!,
        urlExpiresAt: mapValueOfType<String>(json, r'url_expires_at')!,
      );
    }
    return null;
  }

  static List<SnapshotFile> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <SnapshotFile>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = SnapshotFile.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, SnapshotFile> mapFromJson(dynamic json) {
    final map = <String, SnapshotFile>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = SnapshotFile.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of SnapshotFile-objects as value to a dart map
  static Map<String, List<SnapshotFile>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<SnapshotFile>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = SnapshotFile.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'bytes',
    'sha256',
    'url',
    'url_expires_at',
  };
}

