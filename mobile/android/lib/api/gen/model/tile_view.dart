//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class TileView {
  /// Returns a new [TileView] instance.
  TileView({
    this.eyeMm = const [],
    required this.facePx,
    required this.faces,
    this.levels = const [],
    required this.tilePx,
    this.title,
    required this.view,
  });

  List<num>? eyeMm;

  int facePx;

  TileFaces faces;

  List<int> levels;

  int tilePx;

  String? title;

  String view;

  @override
  bool operator ==(Object other) => identical(this, other) || other is TileView &&
    _deepEquality.equals(other.eyeMm, eyeMm) &&
    other.facePx == facePx &&
    other.faces == faces &&
    _deepEquality.equals(other.levels, levels) &&
    other.tilePx == tilePx &&
    other.title == title &&
    other.view == view;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (eyeMm == null ? 0 : eyeMm!.hashCode) +
    (facePx.hashCode) +
    (faces.hashCode) +
    (levels.hashCode) +
    (tilePx.hashCode) +
    (title == null ? 0 : title!.hashCode) +
    (view.hashCode);

  @override
  String toString() => 'TileView[eyeMm=$eyeMm, facePx=$facePx, faces=$faces, levels=$levels, tilePx=$tilePx, title=$title, view=$view]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.eyeMm != null) {
      json[r'eye_mm'] = this.eyeMm;
    } else {
      json[r'eye_mm'] = null;
    }
      json[r'face_px'] = this.facePx;
      json[r'faces'] = this.faces;
      json[r'levels'] = this.levels;
      json[r'tile_px'] = this.tilePx;
    if (this.title != null) {
      json[r'title'] = this.title;
    } else {
      json[r'title'] = null;
    }
      json[r'view'] = this.view;
    return json;
  }

  /// Returns a new [TileView] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static TileView? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'face_px'), 'Required key "TileView[face_px]" is missing from JSON.');
        assert(json[r'face_px'] != null, 'Required key "TileView[face_px]" has a null value in JSON.');
        assert(json.containsKey(r'faces'), 'Required key "TileView[faces]" is missing from JSON.');
        assert(json[r'faces'] != null, 'Required key "TileView[faces]" has a null value in JSON.');
        assert(json.containsKey(r'levels'), 'Required key "TileView[levels]" is missing from JSON.');
        assert(json[r'levels'] != null, 'Required key "TileView[levels]" has a null value in JSON.');
        assert(json.containsKey(r'tile_px'), 'Required key "TileView[tile_px]" is missing from JSON.');
        assert(json[r'tile_px'] != null, 'Required key "TileView[tile_px]" has a null value in JSON.');
        assert(json.containsKey(r'view'), 'Required key "TileView[view]" is missing from JSON.');
        assert(json[r'view'] != null, 'Required key "TileView[view]" has a null value in JSON.');
        return true;
      }());

      return TileView(
        eyeMm: json[r'eye_mm'] is Iterable
            ? (json[r'eye_mm'] as Iterable).cast<num>().toList(growable: false)
            : const [],
        facePx: mapValueOfType<int>(json, r'face_px')!,
        faces: TileFaces.fromJson(json[r'faces'])!,
        levels: json[r'levels'] is Iterable
            ? (json[r'levels'] as Iterable).cast<int>().toList(growable: false)
            : const [],
        tilePx: mapValueOfType<int>(json, r'tile_px')!,
        title: mapValueOfType<String>(json, r'title'),
        view: mapValueOfType<String>(json, r'view')!,
      );
    }
    return null;
  }

  static List<TileView> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <TileView>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = TileView.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, TileView> mapFromJson(dynamic json) {
    final map = <String, TileView>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = TileView.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of TileView-objects as value to a dart map
  static Map<String, List<TileView>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<TileView>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = TileView.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'face_px',
    'faces',
    'levels',
    'tile_px',
    'view',
  };
}

