//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class Snapshot {
  /// Returns a new [Snapshot] instance.
  Snapshot({
    required this.atSeq,
    required this.createdAt,
    required this.createdBy,
    required this.docVersion,
    required this.files,
    required this.snapshotId,
  });

  int atSeq;

  String createdAt;

  int? createdBy;

  int docVersion;

  SnapshotFiles files;

  String snapshotId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is Snapshot &&
    other.atSeq == atSeq &&
    other.createdAt == createdAt &&
    other.createdBy == createdBy &&
    other.docVersion == docVersion &&
    other.files == files &&
    other.snapshotId == snapshotId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (atSeq.hashCode) +
    (createdAt.hashCode) +
    (createdBy == null ? 0 : createdBy!.hashCode) +
    (docVersion.hashCode) +
    (files.hashCode) +
    (snapshotId.hashCode);

  @override
  String toString() => 'Snapshot[atSeq=$atSeq, createdAt=$createdAt, createdBy=$createdBy, docVersion=$docVersion, files=$files, snapshotId=$snapshotId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'at_seq'] = this.atSeq;
      json[r'created_at'] = this.createdAt;
    if (this.createdBy != null) {
      json[r'created_by'] = this.createdBy;
    } else {
      json[r'created_by'] = null;
    }
      json[r'doc_version'] = this.docVersion;
      json[r'files'] = this.files;
      json[r'snapshot_id'] = this.snapshotId;
    return json;
  }

  /// Returns a new [Snapshot] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static Snapshot? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'at_seq'), 'Required key "Snapshot[at_seq]" is missing from JSON.');
        assert(json[r'at_seq'] != null, 'Required key "Snapshot[at_seq]" has a null value in JSON.');
        assert(json.containsKey(r'created_at'), 'Required key "Snapshot[created_at]" is missing from JSON.');
        assert(json[r'created_at'] != null, 'Required key "Snapshot[created_at]" has a null value in JSON.');
        assert(json.containsKey(r'created_by'), 'Required key "Snapshot[created_by]" is missing from JSON.');
        assert(json.containsKey(r'doc_version'), 'Required key "Snapshot[doc_version]" is missing from JSON.');
        assert(json[r'doc_version'] != null, 'Required key "Snapshot[doc_version]" has a null value in JSON.');
        assert(json.containsKey(r'files'), 'Required key "Snapshot[files]" is missing from JSON.');
        assert(json[r'files'] != null, 'Required key "Snapshot[files]" has a null value in JSON.');
        assert(json.containsKey(r'snapshot_id'), 'Required key "Snapshot[snapshot_id]" is missing from JSON.');
        assert(json[r'snapshot_id'] != null, 'Required key "Snapshot[snapshot_id]" has a null value in JSON.');
        return true;
      }());

      return Snapshot(
        atSeq: mapValueOfType<int>(json, r'at_seq')!,
        createdAt: mapValueOfType<String>(json, r'created_at')!,
        createdBy: mapValueOfType<int>(json, r'created_by'),
        docVersion: mapValueOfType<int>(json, r'doc_version')!,
        files: SnapshotFiles.fromJson(json[r'files'])!,
        snapshotId: mapValueOfType<String>(json, r'snapshot_id')!,
      );
    }
    return null;
  }

  static List<Snapshot> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <Snapshot>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = Snapshot.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, Snapshot> mapFromJson(dynamic json) {
    final map = <String, Snapshot>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = Snapshot.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of Snapshot-objects as value to a dart map
  static Map<String, List<Snapshot>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<Snapshot>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = Snapshot.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'at_seq',
    'created_at',
    'created_by',
    'doc_version',
    'files',
    'snapshot_id',
  };
}

