//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class PullPage {
  /// Returns a new [PullPage] instance.
  PullPage({
    required this.headSeq,
    required this.more,
    this.ops = const [],
  });

  int headSeq;

  bool more;

  List<Operation> ops;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PullPage &&
    other.headSeq == headSeq &&
    other.more == more &&
    _deepEquality.equals(other.ops, ops);

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (headSeq.hashCode) +
    (more.hashCode) +
    (ops.hashCode);

  @override
  String toString() => 'PullPage[headSeq=$headSeq, more=$more, ops=$ops]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'head_seq'] = this.headSeq;
      json[r'more'] = this.more;
      json[r'ops'] = this.ops;
    return json;
  }

  /// Returns a new [PullPage] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PullPage? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'head_seq'), 'Required key "PullPage[head_seq]" is missing from JSON.');
        assert(json[r'head_seq'] != null, 'Required key "PullPage[head_seq]" has a null value in JSON.');
        assert(json.containsKey(r'more'), 'Required key "PullPage[more]" is missing from JSON.');
        assert(json[r'more'] != null, 'Required key "PullPage[more]" has a null value in JSON.');
        assert(json.containsKey(r'ops'), 'Required key "PullPage[ops]" is missing from JSON.');
        assert(json[r'ops'] != null, 'Required key "PullPage[ops]" has a null value in JSON.');
        return true;
      }());

      return PullPage(
        headSeq: mapValueOfType<int>(json, r'head_seq')!,
        more: mapValueOfType<bool>(json, r'more')!,
        ops: Operation.listFromJson(json[r'ops']),
      );
    }
    return null;
  }

  static List<PullPage> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PullPage>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PullPage.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PullPage> mapFromJson(dynamic json) {
    final map = <String, PullPage>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PullPage.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PullPage-objects as value to a dart map
  static Map<String, List<PullPage>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PullPage>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PullPage.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'head_seq',
    'more',
    'ops',
  };
}

