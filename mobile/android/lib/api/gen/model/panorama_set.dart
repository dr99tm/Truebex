//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PanoramaSet {
  /// Returns a new [PanoramaSet] instance.
  PanoramaSet({
    required this.atSeq,
    required this.following,
    required this.mine,
    required this.rev,
    required this.setId,
    required this.updatedAt,
    this.views = const [],
  });

  int atSeq;

  bool following;

  bool mine;

  int rev;

  String setId;

  String updatedAt;

  List<String> views;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PanoramaSet &&
    other.atSeq == atSeq &&
    other.following == following &&
    other.mine == mine &&
    other.rev == rev &&
    other.setId == setId &&
    other.updatedAt == updatedAt &&
    _deepEquality.equals(other.views, views);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (atSeq.hashCode) +
    (following.hashCode) +
    (mine.hashCode) +
    (rev.hashCode) +
    (setId.hashCode) +
    (updatedAt.hashCode) +
    (views.hashCode);

  @override
  String toString() => 'PanoramaSet[atSeq=$atSeq, following=$following, mine=$mine, rev=$rev, setId=$setId, updatedAt=$updatedAt, views=$views]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'at_seq'] = this.atSeq;
      json[r'following'] = this.following;
      json[r'mine'] = this.mine;
      json[r'rev'] = this.rev;
      json[r'set_id'] = this.setId;
      json[r'updated_at'] = this.updatedAt;
      json[r'views'] = this.views;
    return json;
  }

  /// Returns a new [PanoramaSet] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PanoramaSet? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'at_seq'), 'Required key "PanoramaSet[at_seq]" is missing from JSON.');
        assert(json[r'at_seq'] != null, 'Required key "PanoramaSet[at_seq]" has a null value in JSON.');
        assert(json.containsKey(r'following'), 'Required key "PanoramaSet[following]" is missing from JSON.');
        assert(json[r'following'] != null, 'Required key "PanoramaSet[following]" has a null value in JSON.');
        assert(json.containsKey(r'mine'), 'Required key "PanoramaSet[mine]" is missing from JSON.');
        assert(json[r'mine'] != null, 'Required key "PanoramaSet[mine]" has a null value in JSON.');
        assert(json.containsKey(r'rev'), 'Required key "PanoramaSet[rev]" is missing from JSON.');
        assert(json[r'rev'] != null, 'Required key "PanoramaSet[rev]" has a null value in JSON.');
        assert(json.containsKey(r'set_id'), 'Required key "PanoramaSet[set_id]" is missing from JSON.');
        assert(json[r'set_id'] != null, 'Required key "PanoramaSet[set_id]" has a null value in JSON.');
        assert(json.containsKey(r'updated_at'), 'Required key "PanoramaSet[updated_at]" is missing from JSON.');
        assert(json[r'updated_at'] != null, 'Required key "PanoramaSet[updated_at]" has a null value in JSON.');
        assert(json.containsKey(r'views'), 'Required key "PanoramaSet[views]" is missing from JSON.');
        assert(json[r'views'] != null, 'Required key "PanoramaSet[views]" has a null value in JSON.');
        return true;
      }());

      return PanoramaSet(
        atSeq: mapValueOfType<int>(json, r'at_seq')!,
        following: mapValueOfType<bool>(json, r'following')!,
        mine: mapValueOfType<bool>(json, r'mine')!,
        rev: mapValueOfType<int>(json, r'rev')!,
        setId: mapValueOfType<String>(json, r'set_id')!,
        updatedAt: mapValueOfType<String>(json, r'updated_at')!,
        views: json[r'views'] is Iterable
            ? (json[r'views'] as Iterable).cast<String>().toList(growable: false)
            : const [],
      );
    }
    return null;
  }

  static List<PanoramaSet> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PanoramaSet>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PanoramaSet.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PanoramaSet> mapFromJson(dynamic json) {
    final map = <String, PanoramaSet>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PanoramaSet.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PanoramaSet-objects as value to a dart map
  static Map<String, List<PanoramaSet>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PanoramaSet>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PanoramaSet.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'at_seq',
    'following',
    'mine',
    'rev',
    'set_id',
    'updated_at',
    'views',
  };
}

