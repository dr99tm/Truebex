//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class SnapshotSummary {
  /// Returns a new [SnapshotSummary] instance.
  SnapshotSummary({
    required this.atSeq,
    required this.createdAt,
    required this.docVersion,
    required this.snapshotId,
  });

  int atSeq;

  String createdAt;

  int docVersion;

  String snapshotId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is SnapshotSummary &&
    other.atSeq == atSeq &&
    other.createdAt == createdAt &&
    other.docVersion == docVersion &&
    other.snapshotId == snapshotId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (atSeq.hashCode) +
    (createdAt.hashCode) +
    (docVersion.hashCode) +
    (snapshotId.hashCode);

  @override
  String toString() => 'SnapshotSummary[atSeq=$atSeq, createdAt=$createdAt, docVersion=$docVersion, snapshotId=$snapshotId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'at_seq'] = this.atSeq;
      json[r'created_at'] = this.createdAt;
      json[r'doc_version'] = this.docVersion;
      json[r'snapshot_id'] = this.snapshotId;
    return json;
  }

  /// Returns a new [SnapshotSummary] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static SnapshotSummary? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'at_seq'), 'Required key "SnapshotSummary[at_seq]" is missing from JSON.');
        assert(json[r'at_seq'] != null, 'Required key "SnapshotSummary[at_seq]" has a null value in JSON.');
        assert(json.containsKey(r'created_at'), 'Required key "SnapshotSummary[created_at]" is missing from JSON.');
        assert(json[r'created_at'] != null, 'Required key "SnapshotSummary[created_at]" has a null value in JSON.');
        assert(json.containsKey(r'doc_version'), 'Required key "SnapshotSummary[doc_version]" is missing from JSON.');
        assert(json[r'doc_version'] != null, 'Required key "SnapshotSummary[doc_version]" has a null value in JSON.');
        assert(json.containsKey(r'snapshot_id'), 'Required key "SnapshotSummary[snapshot_id]" is missing from JSON.');
        assert(json[r'snapshot_id'] != null, 'Required key "SnapshotSummary[snapshot_id]" has a null value in JSON.');
        return true;
      }());

      return SnapshotSummary(
        atSeq: mapValueOfType<int>(json, r'at_seq')!,
        createdAt: mapValueOfType<String>(json, r'created_at')!,
        docVersion: mapValueOfType<int>(json, r'doc_version')!,
        snapshotId: mapValueOfType<String>(json, r'snapshot_id')!,
      );
    }
    return null;
  }

  static List<SnapshotSummary> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <SnapshotSummary>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = SnapshotSummary.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, SnapshotSummary> mapFromJson(dynamic json) {
    final map = <String, SnapshotSummary>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = SnapshotSummary.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of SnapshotSummary-objects as value to a dart map
  static Map<String, List<SnapshotSummary>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<SnapshotSummary>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = SnapshotSummary.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'at_seq',
    'created_at',
    'doc_version',
    'snapshot_id',
  };
}

