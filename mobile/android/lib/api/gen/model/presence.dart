//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class Presence {
  /// Returns a new [Presence] instance.
  Presence({
    required this.client,
    this.editing = const [],
    required this.name,
    required this.replicaId,
    required this.seenAt,
    this.selection = const [],
    required this.userId,
    required this.view,
  });

  String client;

  List<String> editing;

  String? name;

  String replicaId;

  String seenAt;

  List<String> selection;

  int userId;

  PresenceView? view;

  @override
  bool operator ==(Object other) => identical(this, other) || other is Presence &&
    other.client == client &&
    _deepEquality.equals(other.editing, editing) &&
    other.name == name &&
    other.replicaId == replicaId &&
    other.seenAt == seenAt &&
    _deepEquality.equals(other.selection, selection) &&
    other.userId == userId &&
    other.view == view;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (client.hashCode) +
    (editing.hashCode) +
    (name == null ? 0 : name!.hashCode) +
    (replicaId.hashCode) +
    (seenAt.hashCode) +
    (selection.hashCode) +
    (userId.hashCode) +
    (view == null ? 0 : view!.hashCode);

  @override
  String toString() => 'Presence[client=$client, editing=$editing, name=$name, replicaId=$replicaId, seenAt=$seenAt, selection=$selection, userId=$userId, view=$view]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'client'] = this.client;
      json[r'editing'] = this.editing;
    if (this.name != null) {
      json[r'name'] = this.name;
    } else {
      json[r'name'] = null;
    }
      json[r'replica_id'] = this.replicaId;
      json[r'seen_at'] = this.seenAt;
      json[r'selection'] = this.selection;
      json[r'user_id'] = this.userId;
    if (this.view != null) {
      json[r'view'] = this.view;
    } else {
      json[r'view'] = null;
    }
    return json;
  }

  /// Returns a new [Presence] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static Presence? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'client'), 'Required key "Presence[client]" is missing from JSON.');
        assert(json[r'client'] != null, 'Required key "Presence[client]" has a null value in JSON.');
        assert(json.containsKey(r'editing'), 'Required key "Presence[editing]" is missing from JSON.');
        assert(json[r'editing'] != null, 'Required key "Presence[editing]" has a null value in JSON.');
        assert(json.containsKey(r'name'), 'Required key "Presence[name]" is missing from JSON.');
        assert(json.containsKey(r'replica_id'), 'Required key "Presence[replica_id]" is missing from JSON.');
        assert(json[r'replica_id'] != null, 'Required key "Presence[replica_id]" has a null value in JSON.');
        assert(json.containsKey(r'seen_at'), 'Required key "Presence[seen_at]" is missing from JSON.');
        assert(json[r'seen_at'] != null, 'Required key "Presence[seen_at]" has a null value in JSON.');
        assert(json.containsKey(r'selection'), 'Required key "Presence[selection]" is missing from JSON.');
        assert(json[r'selection'] != null, 'Required key "Presence[selection]" has a null value in JSON.');
        assert(json.containsKey(r'user_id'), 'Required key "Presence[user_id]" is missing from JSON.');
        assert(json[r'user_id'] != null, 'Required key "Presence[user_id]" has a null value in JSON.');
        assert(json.containsKey(r'view'), 'Required key "Presence[view]" is missing from JSON.');
        return true;
      }());

      return Presence(
        client: mapValueOfType<String>(json, r'client')!,
        editing: json[r'editing'] is Iterable
            ? (json[r'editing'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        name: mapValueOfType<String>(json, r'name'),
        replicaId: mapValueOfType<String>(json, r'replica_id')!,
        seenAt: mapValueOfType<String>(json, r'seen_at')!,
        selection: json[r'selection'] is Iterable
            ? (json[r'selection'] as Iterable).cast<String>().toList(growable: false)
            : const [],
        userId: mapValueOfType<int>(json, r'user_id')!,
        view: PresenceView.fromJson(json[r'view']),
      );
    }
    return null;
  }

  static List<Presence> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <Presence>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = Presence.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, Presence> mapFromJson(dynamic json) {
    final map = <String, Presence>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = Presence.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of Presence-objects as value to a dart map
  static Map<String, List<Presence>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<Presence>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = Presence.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'client',
    'editing',
    'name',
    'replica_id',
    'seen_at',
    'selection',
    'user_id',
    'view',
  };
}

