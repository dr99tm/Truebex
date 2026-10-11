//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class MemberList {
  /// Returns a new [MemberList] instance.
  MemberList({
    this.members = const [],
  });

  List<Member> members;

  @override
  bool operator ==(Object other) => identical(this, other) || other is MemberList &&
    _deepEquality.equals(other.members, members);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (members.hashCode);

  @override
  String toString() => 'MemberList[members=$members]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'members'] = this.members;
    return json;
  }

  /// Returns a new [MemberList] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static MemberList? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'members'), 'Required key "MemberList[members]" is missing from JSON.');
        assert(json[r'members'] != null, 'Required key "MemberList[members]" has a null value in JSON.');
        return true;
      }());

      return MemberList(
        members: Member.listFromJson(json[r'members']),
      );
    }
    return null;
  }

  static List<MemberList> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <MemberList>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = MemberList.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, MemberList> mapFromJson(dynamic json) {
    final map = <String, MemberList>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = MemberList.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of MemberList-objects as value to a dart map
  static Map<String, List<MemberList>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<MemberList>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = MemberList.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'members',
  };
}

