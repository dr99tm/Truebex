//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class OperationAction {
  /// Returns a new [OperationAction] instance.
  OperationAction({
    required this.args,
    required this.permission,
    required this.requestId,
    required this.session,
    required this.tool,
  });

  Object args;

  String permission;

  String requestId;

  String session;

  String tool;

  @override
  bool operator ==(Object other) => identical(this, other) || other is OperationAction &&
    other.args == args &&
    other.permission == permission &&
    other.requestId == requestId &&
    other.session == session &&
    other.tool == tool;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (args.hashCode) +
    (permission.hashCode) +
    (requestId.hashCode) +
    (session.hashCode) +
    (tool.hashCode);

  @override
  String toString() => 'OperationAction[args=$args, permission=$permission, requestId=$requestId, session=$session, tool=$tool]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'args'] = this.args;
      json[r'permission'] = this.permission;
      json[r'request_id'] = this.requestId;
      json[r'session'] = this.session;
      json[r'tool'] = this.tool;
    return json;
  }

  /// Returns a new [OperationAction] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static OperationAction? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'args'), 'Required key "OperationAction[args]" is missing from JSON.');
        assert(json[r'args'] != null, 'Required key "OperationAction[args]" has a null value in JSON.');
        assert(json.containsKey(r'permission'), 'Required key "OperationAction[permission]" is missing from JSON.');
        assert(json[r'permission'] != null, 'Required key "OperationAction[permission]" has a null value in JSON.');
        assert(json.containsKey(r'request_id'), 'Required key "OperationAction[request_id]" is missing from JSON.');
        assert(json[r'request_id'] != null, 'Required key "OperationAction[request_id]" has a null value in JSON.');
        assert(json.containsKey(r'session'), 'Required key "OperationAction[session]" is missing from JSON.');
        assert(json[r'session'] != null, 'Required key "OperationAction[session]" has a null value in JSON.');
        assert(json.containsKey(r'tool'), 'Required key "OperationAction[tool]" is missing from JSON.');
        assert(json[r'tool'] != null, 'Required key "OperationAction[tool]" has a null value in JSON.');
        return true;
      }());

      return OperationAction(
        args: mapValueOfType<Object>(json, r'args')!,
        permission: mapValueOfType<String>(json, r'permission')!,
        requestId: mapValueOfType<String>(json, r'request_id')!,
        session: mapValueOfType<String>(json, r'session')!,
        tool: mapValueOfType<String>(json, r'tool')!,
      );
    }
    return null;
  }

  static List<OperationAction> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <OperationAction>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = OperationAction.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, OperationAction> mapFromJson(dynamic json) {
    final map = <String, OperationAction>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = OperationAction.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of OperationAction-objects as value to a dart map
  static Map<String, List<OperationAction>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<OperationAction>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = OperationAction.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'args',
    'permission',
    'request_id',
    'session',
    'tool',
  };
}

