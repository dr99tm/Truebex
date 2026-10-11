//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class SetState {
  /// Returns a new [SetState] instance.
  SetState({
    required this.atSeq,
    required this.followJobId,
    required this.following,
    required this.jobId,
    required this.manifest,
    required this.rev,
  });

  int atSeq;

  String followJobId;

  bool following;

  String? jobId;

  TileManifest? manifest;

  int rev;

  @override
  bool operator ==(Object other) => identical(this, other) || other is SetState &&
    other.atSeq == atSeq &&
    other.followJobId == followJobId &&
    other.following == following &&
    other.jobId == jobId &&
    other.manifest == manifest &&
    other.rev == rev;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (atSeq.hashCode) +
    (followJobId.hashCode) +
    (following.hashCode) +
    (jobId == null ? 0 : jobId!.hashCode) +
    (manifest == null ? 0 : manifest!.hashCode) +
    (rev.hashCode);

  @override
  String toString() => 'SetState[atSeq=$atSeq, followJobId=$followJobId, following=$following, jobId=$jobId, manifest=$manifest, rev=$rev]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'at_seq'] = this.atSeq;
      json[r'follow_job_id'] = this.followJobId;
      json[r'following'] = this.following;
    if (this.jobId != null) {
      json[r'job_id'] = this.jobId;
    } else {
      json[r'job_id'] = null;
    }
    if (this.manifest != null) {
      json[r'manifest'] = this.manifest;
    } else {
      json[r'manifest'] = null;
    }
      json[r'rev'] = this.rev;
    return json;
  }

  /// Returns a new [SetState] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static SetState? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'at_seq'), 'Required key "SetState[at_seq]" is missing from JSON.');
        assert(json[r'at_seq'] != null, 'Required key "SetState[at_seq]" has a null value in JSON.');
        assert(json.containsKey(r'follow_job_id'), 'Required key "SetState[follow_job_id]" is missing from JSON.');
        assert(json[r'follow_job_id'] != null, 'Required key "SetState[follow_job_id]" has a null value in JSON.');
        assert(json.containsKey(r'following'), 'Required key "SetState[following]" is missing from JSON.');
        assert(json[r'following'] != null, 'Required key "SetState[following]" has a null value in JSON.');
        assert(json.containsKey(r'job_id'), 'Required key "SetState[job_id]" is missing from JSON.');
        assert(json.containsKey(r'manifest'), 'Required key "SetState[manifest]" is missing from JSON.');
        assert(json.containsKey(r'rev'), 'Required key "SetState[rev]" is missing from JSON.');
        assert(json[r'rev'] != null, 'Required key "SetState[rev]" has a null value in JSON.');
        return true;
      }());

      return SetState(
        atSeq: mapValueOfType<int>(json, r'at_seq')!,
        followJobId: mapValueOfType<String>(json, r'follow_job_id')!,
        following: mapValueOfType<bool>(json, r'following')!,
        jobId: mapValueOfType<String>(json, r'job_id'),
        manifest: TileManifest.fromJson(json[r'manifest']),
        rev: mapValueOfType<int>(json, r'rev')!,
      );
    }
    return null;
  }

  static List<SetState> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <SetState>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = SetState.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, SetState> mapFromJson(dynamic json) {
    final map = <String, SetState>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = SetState.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of SetState-objects as value to a dart map
  static Map<String, List<SetState>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<SetState>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = SetState.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'at_seq',
    'follow_job_id',
    'following',
    'job_id',
    'manifest',
    'rev',
  };
}

