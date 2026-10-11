//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class TileFaces {
  /// Returns a new [TileFaces] instance.
  TileFaces({
    required this.d,
    required this.e,
    required this.n,
    required this.s,
    required this.u,
    required this.w,
  });

  TileFace d;

  TileFace e;

  TileFace n;

  TileFace s;

  TileFace u;

  TileFace w;

  @override
  bool operator ==(Object other) => identical(this, other) || other is TileFaces &&
    other.d == d &&
    other.e == e &&
    other.n == n &&
    other.s == s &&
    other.u == u &&
    other.w == w;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (d.hashCode) +
    (e.hashCode) +
    (n.hashCode) +
    (s.hashCode) +
    (u.hashCode) +
    (w.hashCode);

  @override
  String toString() => 'TileFaces[d=$d, e=$e, n=$n, s=$s, u=$u, w=$w]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'd'] = this.d;
      json[r'e'] = this.e;
      json[r'n'] = this.n;
      json[r's'] = this.s;
      json[r'u'] = this.u;
      json[r'w'] = this.w;
    return json;
  }

  /// Returns a new [TileFaces] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static TileFaces? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'd'), 'Required key "TileFaces[d]" is missing from JSON.');
        assert(json[r'd'] != null, 'Required key "TileFaces[d]" has a null value in JSON.');
        assert(json.containsKey(r'e'), 'Required key "TileFaces[e]" is missing from JSON.');
        assert(json[r'e'] != null, 'Required key "TileFaces[e]" has a null value in JSON.');
        assert(json.containsKey(r'n'), 'Required key "TileFaces[n]" is missing from JSON.');
        assert(json[r'n'] != null, 'Required key "TileFaces[n]" has a null value in JSON.');
        assert(json.containsKey(r's'), 'Required key "TileFaces[s]" is missing from JSON.');
        assert(json[r's'] != null, 'Required key "TileFaces[s]" has a null value in JSON.');
        assert(json.containsKey(r'u'), 'Required key "TileFaces[u]" is missing from JSON.');
        assert(json[r'u'] != null, 'Required key "TileFaces[u]" has a null value in JSON.');
        assert(json.containsKey(r'w'), 'Required key "TileFaces[w]" is missing from JSON.');
        assert(json[r'w'] != null, 'Required key "TileFaces[w]" has a null value in JSON.');
        return true;
      }());

      return TileFaces(
        d: TileFace.fromJson(json[r'd'])!,
        e: TileFace.fromJson(json[r'e'])!,
        n: TileFace.fromJson(json[r'n'])!,
        s: TileFace.fromJson(json[r's'])!,
        u: TileFace.fromJson(json[r'u'])!,
        w: TileFace.fromJson(json[r'w'])!,
      );
    }
    return null;
  }

  static List<TileFaces> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <TileFaces>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = TileFaces.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, TileFaces> mapFromJson(dynamic json) {
    final map = <String, TileFaces>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = TileFaces.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of TileFaces-objects as value to a dart map
  static Map<String, List<TileFaces>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<TileFaces>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = TileFaces.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'd',
    'e',
    'n',
    's',
    'u',
    'w',
  };
}

