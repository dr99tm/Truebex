//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class ProjectList {
  /// Returns a new [ProjectList] instance.
  ProjectList({
    required this.nextCursor,
    this.projects = const [],
  });

  String? nextCursor;

  List<ProjectRecord> projects;

  @override
  bool operator ==(Object other) => identical(this, other) || other is ProjectList &&
    other.nextCursor == nextCursor &&
    _deepEquality.equals(other.projects, projects);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (nextCursor == null ? 0 : nextCursor!.hashCode) +
    (projects.hashCode);

  @override
  String toString() => 'ProjectList[nextCursor=$nextCursor, projects=$projects]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.nextCursor != null) {
      json[r'next_cursor'] = this.nextCursor;
    } else {
      json[r'next_cursor'] = null;
    }
      json[r'projects'] = this.projects;
    return json;
  }

  /// Returns a new [ProjectList] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static ProjectList? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'next_cursor'), 'Required key "ProjectList[next_cursor]" is missing from JSON.');
        assert(json.containsKey(r'projects'), 'Required key "ProjectList[projects]" is missing from JSON.');
        assert(json[r'projects'] != null, 'Required key "ProjectList[projects]" has a null value in JSON.');
        return true;
      }());

      return ProjectList(
        nextCursor: mapValueOfType<String>(json, r'next_cursor'),
        projects: ProjectRecord.listFromJson(json[r'projects']),
      );
    }
    return null;
  }

  static List<ProjectList> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <ProjectList>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = ProjectList.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, ProjectList> mapFromJson(dynamic json) {
    final map = <String, ProjectList>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = ProjectList.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of ProjectList-objects as value to a dart map
  static Map<String, List<ProjectList>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<ProjectList>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = ProjectList.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'next_cursor',
    'projects',
  };
}

