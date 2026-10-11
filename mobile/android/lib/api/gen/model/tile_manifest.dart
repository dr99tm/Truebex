//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class TileManifest {
  /// Returns a new [TileManifest] instance.
  TileManifest({
    required this.atSeq,
    this.facesRendered,
    this.facesReused,
    required this.jobId,
    this.projectId,
    required this.schema,
    required this.tilesBase,
    this.views = const [],
  });

  int atSeq;

  int? facesRendered;

  int? facesReused;

  String jobId;

  String? projectId;

  String schema;

  String tilesBase;

  List<TileView> views;

  @override
  bool operator ==(Object other) => identical(this, other) || other is TileManifest &&
    other.atSeq == atSeq &&
    other.facesRendered == facesRendered &&
    other.facesReused == facesReused &&
    other.jobId == jobId &&
    other.projectId == projectId &&
    other.schema == schema &&
    other.tilesBase == tilesBase &&
    _deepEquality.equals(other.views, views);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (atSeq.hashCode) +
    (facesRendered == null ? 0 : facesRendered!.hashCode) +
    (facesReused == null ? 0 : facesReused!.hashCode) +
    (jobId.hashCode) +
    (projectId == null ? 0 : projectId!.hashCode) +
    (schema.hashCode) +
    (tilesBase.hashCode) +
    (views.hashCode);

  @override
  String toString() => 'TileManifest[atSeq=$atSeq, facesRendered=$facesRendered, facesReused=$facesReused, jobId=$jobId, projectId=$projectId, schema=$schema, tilesBase=$tilesBase, views=$views]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'at_seq'] = this.atSeq;
    if (this.facesRendered != null) {
      json[r'faces_rendered'] = this.facesRendered;
    } else {
      json[r'faces_rendered'] = null;
    }
    if (this.facesReused != null) {
      json[r'faces_reused'] = this.facesReused;
    } else {
      json[r'faces_reused'] = null;
    }
      json[r'job_id'] = this.jobId;
    if (this.projectId != null) {
      json[r'project_id'] = this.projectId;
    } else {
      json[r'project_id'] = null;
    }
      json[r'schema'] = this.schema;
      json[r'tiles_base'] = this.tilesBase;
      json[r'views'] = this.views;
    return json;
  }

  /// Returns a new [TileManifest] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static TileManifest? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'at_seq'), 'Required key "TileManifest[at_seq]" is missing from JSON.');
        assert(json[r'at_seq'] != null, 'Required key "TileManifest[at_seq]" has a null value in JSON.');
        assert(json.containsKey(r'job_id'), 'Required key "TileManifest[job_id]" is missing from JSON.');
        assert(json[r'job_id'] != null, 'Required key "TileManifest[job_id]" has a null value in JSON.');
        assert(json.containsKey(r'schema'), 'Required key "TileManifest[schema]" is missing from JSON.');
        assert(json[r'schema'] != null, 'Required key "TileManifest[schema]" has a null value in JSON.');
        assert(json.containsKey(r'tiles_base'), 'Required key "TileManifest[tiles_base]" is missing from JSON.');
        assert(json[r'tiles_base'] != null, 'Required key "TileManifest[tiles_base]" has a null value in JSON.');
        assert(json.containsKey(r'views'), 'Required key "TileManifest[views]" is missing from JSON.');
        assert(json[r'views'] != null, 'Required key "TileManifest[views]" has a null value in JSON.');
        return true;
      }());

      return TileManifest(
        atSeq: mapValueOfType<int>(json, r'at_seq')!,
        facesRendered: mapValueOfType<int>(json, r'faces_rendered'),
        facesReused: mapValueOfType<int>(json, r'faces_reused'),
        jobId: mapValueOfType<String>(json, r'job_id')!,
        projectId: mapValueOfType<String>(json, r'project_id'),
        schema: mapValueOfType<String>(json, r'schema')!,
        tilesBase: mapValueOfType<String>(json, r'tiles_base')!,
        views: TileView.listFromJson(json[r'views']),
      );
    }
    return null;
  }

  static List<TileManifest> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <TileManifest>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = TileManifest.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, TileManifest> mapFromJson(dynamic json) {
    final map = <String, TileManifest>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = TileManifest.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of TileManifest-objects as value to a dart map
  static Map<String, List<TileManifest>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<TileManifest>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = TileManifest.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'at_seq',
    'job_id',
    'schema',
    'tiles_base',
    'views',
  };
}

