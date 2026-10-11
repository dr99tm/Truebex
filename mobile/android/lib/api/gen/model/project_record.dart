//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class ProjectRecord {
  /// Returns a new [ProjectRecord] instance.
  ProjectRecord({
    required this.bytes,
    required this.createdAt,
    required this.docVersion,
    required this.headSeq,
    required this.latestSnapshot,
    required this.members,
    required this.name,
    required this.orgId,
    required this.owner,
    required this.projectId,
    required this.role,
    required this.updatedAt,
  });

  int bytes;

  String createdAt;

  int docVersion;

  int headSeq;

  SnapshotSummary? latestSnapshot;

  int members;

  String name;

  String? orgId;

  ProjectOwner? owner;

  String projectId;

  ProjectRecordRoleEnum role;

  String updatedAt;

  @override
  bool operator ==(Object other) => identical(this, other) || other is ProjectRecord &&
    other.bytes == bytes &&
    other.createdAt == createdAt &&
    other.docVersion == docVersion &&
    other.headSeq == headSeq &&
    other.latestSnapshot == latestSnapshot &&
    other.members == members &&
    other.name == name &&
    other.orgId == orgId &&
    other.owner == owner &&
    other.projectId == projectId &&
    other.role == role &&
    other.updatedAt == updatedAt;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (bytes.hashCode) +
    (createdAt.hashCode) +
    (docVersion.hashCode) +
    (headSeq.hashCode) +
    (latestSnapshot == null ? 0 : latestSnapshot!.hashCode) +
    (members.hashCode) +
    (name.hashCode) +
    (orgId == null ? 0 : orgId!.hashCode) +
    (owner == null ? 0 : owner!.hashCode) +
    (projectId.hashCode) +
    (role.hashCode) +
    (updatedAt.hashCode);

  @override
  String toString() => 'ProjectRecord[bytes=$bytes, createdAt=$createdAt, docVersion=$docVersion, headSeq=$headSeq, latestSnapshot=$latestSnapshot, members=$members, name=$name, orgId=$orgId, owner=$owner, projectId=$projectId, role=$role, updatedAt=$updatedAt]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'bytes'] = this.bytes;
      json[r'created_at'] = this.createdAt;
      json[r'doc_version'] = this.docVersion;
      json[r'head_seq'] = this.headSeq;
    if (this.latestSnapshot != null) {
      json[r'latest_snapshot'] = this.latestSnapshot;
    } else {
      json[r'latest_snapshot'] = null;
    }
      json[r'members'] = this.members;
      json[r'name'] = this.name;
    if (this.orgId != null) {
      json[r'org_id'] = this.orgId;
    } else {
      json[r'org_id'] = null;
    }
    if (this.owner != null) {
      json[r'owner'] = this.owner;
    } else {
      json[r'owner'] = null;
    }
      json[r'project_id'] = this.projectId;
      json[r'role'] = this.role;
      json[r'updated_at'] = this.updatedAt;
    return json;
  }

  /// Returns a new [ProjectRecord] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static ProjectRecord? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'bytes'), 'Required key "ProjectRecord[bytes]" is missing from JSON.');
        assert(json[r'bytes'] != null, 'Required key "ProjectRecord[bytes]" has a null value in JSON.');
        assert(json.containsKey(r'created_at'), 'Required key "ProjectRecord[created_at]" is missing from JSON.');
        assert(json[r'created_at'] != null, 'Required key "ProjectRecord[created_at]" has a null value in JSON.');
        assert(json.containsKey(r'doc_version'), 'Required key "ProjectRecord[doc_version]" is missing from JSON.');
        assert(json[r'doc_version'] != null, 'Required key "ProjectRecord[doc_version]" has a null value in JSON.');
        assert(json.containsKey(r'head_seq'), 'Required key "ProjectRecord[head_seq]" is missing from JSON.');
        assert(json[r'head_seq'] != null, 'Required key "ProjectRecord[head_seq]" has a null value in JSON.');
        assert(json.containsKey(r'latest_snapshot'), 'Required key "ProjectRecord[latest_snapshot]" is missing from JSON.');
        assert(json.containsKey(r'members'), 'Required key "ProjectRecord[members]" is missing from JSON.');
        assert(json[r'members'] != null, 'Required key "ProjectRecord[members]" has a null value in JSON.');
        assert(json.containsKey(r'name'), 'Required key "ProjectRecord[name]" is missing from JSON.');
        assert(json[r'name'] != null, 'Required key "ProjectRecord[name]" has a null value in JSON.');
        assert(json.containsKey(r'org_id'), 'Required key "ProjectRecord[org_id]" is missing from JSON.');
        assert(json.containsKey(r'owner'), 'Required key "ProjectRecord[owner]" is missing from JSON.');
        assert(json.containsKey(r'project_id'), 'Required key "ProjectRecord[project_id]" is missing from JSON.');
        assert(json[r'project_id'] != null, 'Required key "ProjectRecord[project_id]" has a null value in JSON.');
        assert(json.containsKey(r'role'), 'Required key "ProjectRecord[role]" is missing from JSON.');
        assert(json[r'role'] != null, 'Required key "ProjectRecord[role]" has a null value in JSON.');
        assert(json.containsKey(r'updated_at'), 'Required key "ProjectRecord[updated_at]" is missing from JSON.');
        assert(json[r'updated_at'] != null, 'Required key "ProjectRecord[updated_at]" has a null value in JSON.');
        return true;
      }());

      return ProjectRecord(
        bytes: mapValueOfType<int>(json, r'bytes')!,
        createdAt: mapValueOfType<String>(json, r'created_at')!,
        docVersion: mapValueOfType<int>(json, r'doc_version')!,
        headSeq: mapValueOfType<int>(json, r'head_seq')!,
        latestSnapshot: SnapshotSummary.fromJson(json[r'latest_snapshot']),
        members: mapValueOfType<int>(json, r'members')!,
        name: mapValueOfType<String>(json, r'name')!,
        orgId: mapValueOfType<String>(json, r'org_id'),
        owner: ProjectOwner.fromJson(json[r'owner']),
        projectId: mapValueOfType<String>(json, r'project_id')!,
        role: ProjectRecordRoleEnum.fromJson(json[r'role'])!,
        updatedAt: mapValueOfType<String>(json, r'updated_at')!,
      );
    }
    return null;
  }

  static List<ProjectRecord> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <ProjectRecord>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = ProjectRecord.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, ProjectRecord> mapFromJson(dynamic json) {
    final map = <String, ProjectRecord>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = ProjectRecord.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of ProjectRecord-objects as value to a dart map
  static Map<String, List<ProjectRecord>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<ProjectRecord>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = ProjectRecord.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'bytes',
    'created_at',
    'doc_version',
    'head_seq',
    'latest_snapshot',
    'members',
    'name',
    'org_id',
    'owner',
    'project_id',
    'role',
    'updated_at',
  };
}


enum ProjectRecordRoleEnum {
  owner._(r'owner'),
  editor._(r'editor'),
  viewer._(r'viewer'),
  ;

  /// Instantiate a new enum with the provided value.
  const ProjectRecordRoleEnum._(this._value);

  /// The underlying value of this enum member.
  final String _value;

  @override
  String toString() => _value;

  /// Encodes this enum as a value suitable for JSON.
  String toJson() => _value;

  /// Returns the instance of [ProjectRecordRoleEnum] that was successfully decoded
  /// from the passed [value] on success, null otherwise.
  static ProjectRecordRoleEnum? fromJson(dynamic value) => ProjectRecordRoleEnumTypeTransformer().decode(value);

  /// Returns a [List] containing instances of [ProjectRecordRoleEnum]
  /// that were successfully decoded from the passed [JSON][json].
  static List<ProjectRecordRoleEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <ProjectRecordRoleEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = ProjectRecordRoleEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [ProjectRecordRoleEnum] to String,
/// and [decode] dynamic data back to [ProjectRecordRoleEnum].
class ProjectRecordRoleEnumTypeTransformer {
  factory ProjectRecordRoleEnumTypeTransformer() => _instance ??= const ProjectRecordRoleEnumTypeTransformer._();

  const ProjectRecordRoleEnumTypeTransformer._();

  String encode(ProjectRecordRoleEnum data) => data._value;

  /// Returns the instance of [ProjectRecordRoleEnum] that was successfully decoded
  /// from the passed [data] value on success, null otherwise.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  ProjectRecordRoleEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data is ProjectRecordRoleEnum) {
      return data;
    }
    if (data != null) {
      switch (data) {
        case r'owner': return ProjectRecordRoleEnum.owner;
        case r'editor': return ProjectRecordRoleEnum.editor;
        case r'viewer': return ProjectRecordRoleEnum.viewer;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// The singleton instance of this transformer.
  static ProjectRecordRoleEnumTypeTransformer? _instance;
}


