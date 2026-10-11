//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class OpenProject {
  /// Returns a new [OpenProject] instance.
  OpenProject({
    required this.bytes,
    required this.createdAt,
    required this.docVersion,
    required this.headSeq,
    required this.latestSnapshot,
    this.members = const [],
    required this.name,
    required this.orgId,
    required this.owner,
    required this.projectId,
    required this.quota,
    required this.role,
    required this.updatedAt,
  });

  int bytes;

  String createdAt;

  int docVersion;

  int headSeq;

  SnapshotSummary? latestSnapshot;

  List<Member> members;

  String name;

  String? orgId;

  ProjectOwner? owner;

  String projectId;

  ProjectQuota quota;

  OpenProjectRoleEnum role;

  String updatedAt;

  @override
  bool operator ==(Object other) => identical(this, other) || other is OpenProject &&
    other.bytes == bytes &&
    other.createdAt == createdAt &&
    other.docVersion == docVersion &&
    other.headSeq == headSeq &&
    other.latestSnapshot == latestSnapshot &&
    _deepEquality.equals(other.members, members) &&
    other.name == name &&
    other.orgId == orgId &&
    other.owner == owner &&
    other.projectId == projectId &&
    other.quota == quota &&
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
    (quota.hashCode) +
    (role.hashCode) +
    (updatedAt.hashCode);

  @override
  String toString() => 'OpenProject[bytes=$bytes, createdAt=$createdAt, docVersion=$docVersion, headSeq=$headSeq, latestSnapshot=$latestSnapshot, members=$members, name=$name, orgId=$orgId, owner=$owner, projectId=$projectId, quota=$quota, role=$role, updatedAt=$updatedAt]';

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
      json[r'quota'] = this.quota;
      json[r'role'] = this.role;
      json[r'updated_at'] = this.updatedAt;
    return json;
  }

  /// Returns a new [OpenProject] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static OpenProject? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'bytes'), 'Required key "OpenProject[bytes]" is missing from JSON.');
        assert(json[r'bytes'] != null, 'Required key "OpenProject[bytes]" has a null value in JSON.');
        assert(json.containsKey(r'created_at'), 'Required key "OpenProject[created_at]" is missing from JSON.');
        assert(json[r'created_at'] != null, 'Required key "OpenProject[created_at]" has a null value in JSON.');
        assert(json.containsKey(r'doc_version'), 'Required key "OpenProject[doc_version]" is missing from JSON.');
        assert(json[r'doc_version'] != null, 'Required key "OpenProject[doc_version]" has a null value in JSON.');
        assert(json.containsKey(r'head_seq'), 'Required key "OpenProject[head_seq]" is missing from JSON.');
        assert(json[r'head_seq'] != null, 'Required key "OpenProject[head_seq]" has a null value in JSON.');
        assert(json.containsKey(r'latest_snapshot'), 'Required key "OpenProject[latest_snapshot]" is missing from JSON.');
        assert(json.containsKey(r'members'), 'Required key "OpenProject[members]" is missing from JSON.');
        assert(json[r'members'] != null, 'Required key "OpenProject[members]" has a null value in JSON.');
        assert(json.containsKey(r'name'), 'Required key "OpenProject[name]" is missing from JSON.');
        assert(json[r'name'] != null, 'Required key "OpenProject[name]" has a null value in JSON.');
        assert(json.containsKey(r'org_id'), 'Required key "OpenProject[org_id]" is missing from JSON.');
        assert(json.containsKey(r'owner'), 'Required key "OpenProject[owner]" is missing from JSON.');
        assert(json.containsKey(r'project_id'), 'Required key "OpenProject[project_id]" is missing from JSON.');
        assert(json[r'project_id'] != null, 'Required key "OpenProject[project_id]" has a null value in JSON.');
        assert(json.containsKey(r'quota'), 'Required key "OpenProject[quota]" is missing from JSON.');
        assert(json[r'quota'] != null, 'Required key "OpenProject[quota]" has a null value in JSON.');
        assert(json.containsKey(r'role'), 'Required key "OpenProject[role]" is missing from JSON.');
        assert(json[r'role'] != null, 'Required key "OpenProject[role]" has a null value in JSON.');
        assert(json.containsKey(r'updated_at'), 'Required key "OpenProject[updated_at]" is missing from JSON.');
        assert(json[r'updated_at'] != null, 'Required key "OpenProject[updated_at]" has a null value in JSON.');
        return true;
      }());

      return OpenProject(
        bytes: mapValueOfType<int>(json, r'bytes')!,
        createdAt: mapValueOfType<String>(json, r'created_at')!,
        docVersion: mapValueOfType<int>(json, r'doc_version')!,
        headSeq: mapValueOfType<int>(json, r'head_seq')!,
        latestSnapshot: SnapshotSummary.fromJson(json[r'latest_snapshot']),
        members: Member.listFromJson(json[r'members']),
        name: mapValueOfType<String>(json, r'name')!,
        orgId: mapValueOfType<String>(json, r'org_id'),
        owner: ProjectOwner.fromJson(json[r'owner']),
        projectId: mapValueOfType<String>(json, r'project_id')!,
        quota: ProjectQuota.fromJson(json[r'quota'])!,
        role: OpenProjectRoleEnum.fromJson(json[r'role'])!,
        updatedAt: mapValueOfType<String>(json, r'updated_at')!,
      );
    }
    return null;
  }

  static List<OpenProject> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <OpenProject>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = OpenProject.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, OpenProject> mapFromJson(dynamic json) {
    final map = <String, OpenProject>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = OpenProject.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of OpenProject-objects as value to a dart map
  static Map<String, List<OpenProject>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<OpenProject>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = OpenProject.listFromJson(entry.value, growable: growable,);
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
    'quota',
    'role',
    'updated_at',
  };
}


enum OpenProjectRoleEnum {
  owner._(r'owner'),
  editor._(r'editor'),
  viewer._(r'viewer'),
  ;

  /// Instantiate a new enum with the provided value.
  const OpenProjectRoleEnum._(this._value);

  /// The underlying value of this enum member.
  final String _value;

  @override
  String toString() => _value;

  /// Encodes this enum as a value suitable for JSON.
  String toJson() => _value;

  /// Returns the instance of [OpenProjectRoleEnum] that was successfully decoded
  /// from the passed [value] on success, null otherwise.
  static OpenProjectRoleEnum? fromJson(dynamic value) => OpenProjectRoleEnumTypeTransformer().decode(value);

  /// Returns a [List] containing instances of [OpenProjectRoleEnum]
  /// that were successfully decoded from the passed [JSON][json].
  static List<OpenProjectRoleEnum> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <OpenProjectRoleEnum>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = OpenProjectRoleEnum.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }
}

/// Transformation class that can [encode] an instance of [OpenProjectRoleEnum] to String,
/// and [decode] dynamic data back to [OpenProjectRoleEnum].
class OpenProjectRoleEnumTypeTransformer {
  factory OpenProjectRoleEnumTypeTransformer() => _instance ??= const OpenProjectRoleEnumTypeTransformer._();

  const OpenProjectRoleEnumTypeTransformer._();

  String encode(OpenProjectRoleEnum data) => data._value;

  /// Returns the instance of [OpenProjectRoleEnum] that was successfully decoded
  /// from the passed [data] value on success, null otherwise.
  ///
  /// If [allowNull] is true and the [dynamic value][data] cannot be decoded successfully,
  /// then null is returned. However, if [allowNull] is false and the [dynamic value][data]
  /// cannot be decoded successfully, then an [UnimplementedError] is thrown.
  ///
  /// The [allowNull] is very handy when an API changes and a new enum value is added or removed,
  /// and users are still using an old app with the old code.
  OpenProjectRoleEnum? decode(dynamic data, {bool allowNull = true}) {
    if (data is OpenProjectRoleEnum) {
      return data;
    }
    if (data != null) {
      switch (data) {
        case r'owner': return OpenProjectRoleEnum.owner;
        case r'editor': return OpenProjectRoleEnum.editor;
        case r'viewer': return OpenProjectRoleEnum.viewer;
        default:
          if (!allowNull) {
            throw ArgumentError('Unknown enum value to decode: $data');
          }
      }
    }
    return null;
  }

  /// The singleton instance of this transformer.
  static OpenProjectRoleEnumTypeTransformer? _instance;
}


