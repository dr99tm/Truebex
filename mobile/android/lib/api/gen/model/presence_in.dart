//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PresenceIn {
  /// Returns a new [PresenceIn] instance.
  PresenceIn({
    required this.client,
    this.editing = const [],
    this.leaving = false,
    required this.replicaId,
    this.selection = const [],
    this.view,
  });

  String client;

  List<String> editing;

  bool leaving;

  String replicaId;

  List<String> selection;

  ViewIn? view;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PresenceIn &&
    other.client == client &&
    _deepEquality.equals(other.editing, editing) &&
    other.leaving == leaving &&
    other.replicaId == replicaId &&
    _deepEquality.equals(other.selection, selection) &&
    other.view == view;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (client.hashCode) +
    (editing.hashCode) +
    (leaving.hashCode) +
    (replicaId.hashCode) +
    (selection.hashCode) +
    (view == null ? 0 : view!.hashCode);

  @override
  String toString() => 'PresenceIn[client=$client, editing=$editing, leaving=$leaving, replicaId=$replicaId, selection=$selection, view=$view]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'client'] = this.client;
      json[r'editing'] = this.editing;
      json[r'leaving'] = this.leaving;
      json[r'replica_id'] = this.replicaId;
      json[r'selection'] = this.selection;
    if (this.view != null) {
      json[r'view'] = this.view;
    } else {
      json[r'view'] = null;
    }
    return json;
  }

  /// Returns a new [PresenceIn] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PresenceIn? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'client'), 'Required key "PresenceIn[client]" is missing from JSON.');
        assert(json[r'client'] != null, 'Required key "PresenceIn[client]" has a null value in JSON.');
        assert(json.containsKey(r'replica_id'), 'Required key "PresenceIn[replica_id]" is missing from JSON.');
        assert(json[r'replica_id'] != null, 'Required key "PresenceIn[replica_id]" has a null value in JSON.');
        return true;
      }());

      return PresenceIn(
        client: mapValueOfType<String>(json, r'client')!,
        editing: json[r'editing'] is Iterable
            ? (json[r'editing'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        leaving: mapValueOfType<bool>(json, r'leaving') ?? false,
        replicaId: mapValueOfType<String>(json, r'replica_id')!,
        selection: json[r'selection'] is Iterable
            ? (json[r'selection'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        view: ViewIn.fromJson(json[r'view']),
      );
    }
    return null;
  }

  static List<PresenceIn> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PresenceIn>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PresenceIn.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PresenceIn> mapFromJson(dynamic json) {
    final map = <String, PresenceIn>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PresenceIn.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PresenceIn-objects as value to a dart map
  static Map<String, List<PresenceIn>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PresenceIn>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PresenceIn.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'client',
    'replica_id',
  };
}

