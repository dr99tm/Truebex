//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class ProjectOwner {
  /// Returns a new [ProjectOwner] instance.
  ProjectOwner({
    required this.name,
    required this.userId,
  });

  String? name;

  int userId;

  @override
  bool operator ==(Object other) => identical(this, other) || other is ProjectOwner &&
    other.name == name &&
    other.userId == userId;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (name == null ? 0 : name!.hashCode) +
    (userId.hashCode);

  @override
  String toString() => 'ProjectOwner[name=$name, userId=$userId]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.name != null) {
      json[r'name'] = this.name;
    } else {
      json[r'name'] = null;
    }
      json[r'user_id'] = this.userId;
    return json;
  }

  /// Returns a new [ProjectOwner] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static ProjectOwner? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'name'), 'Required key "ProjectOwner[name]" is missing from JSON.');
        assert(json.containsKey(r'user_id'), 'Required key "ProjectOwner[user_id]" is missing from JSON.');
        assert(json[r'user_id'] != null, 'Required key "ProjectOwner[user_id]" has a null value in JSON.');
        return true;
      }());

      return ProjectOwner(
        name: mapValueOfType<String>(json, r'name'),
        userId: mapValueOfType<int>(json, r'user_id')!,
      );
    }
    return null;
  }

  static List<ProjectOwner> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <ProjectOwner>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = ProjectOwner.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, ProjectOwner> mapFromJson(dynamic json) {
    final map = <String, ProjectOwner>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = ProjectOwner.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of ProjectOwner-objects as value to a dart map
  static Map<String, List<ProjectOwner>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<ProjectOwner>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = ProjectOwner.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'name',
    'user_id',
  };
}

