//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;

class ErrorEnvelope {
  /// Returns a new [ErrorEnvelope] instance.
  ErrorEnvelope({
    this.code,
    this.data,
    required this.detail,
    this.requestId,
    this.retryAfterS,
    this.status,
  });

  String? code;

  Object? data;

  String detail;

  String? requestId;

  int? retryAfterS;

  int? status;

  @override
  bool operator ==(Object other) => identical(this, other) || other is ErrorEnvelope &&
    other.code == code &&
    other.data == data &&
    other.detail == detail &&
    other.requestId == requestId &&
    other.retryAfterS == retryAfterS &&
    other.status == status;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (code == null ? 0 : code!.hashCode) +
    (data == null ? 0 : data!.hashCode) +
    (detail.hashCode) +
    (requestId == null ? 0 : requestId!.hashCode) +
    (retryAfterS == null ? 0 : retryAfterS!.hashCode) +
    (status == null ? 0 : status!.hashCode);

  @override
  String toString() => 'ErrorEnvelope[code=$code, data=$data, detail=$detail, requestId=$requestId, retryAfterS=$retryAfterS, status=$status]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.code != null) {
      json[r'code'] = this.code;
    } else {
      json[r'code'] = null;
    }
    if (this.data != null) {
      json[r'data'] = this.data;
    } else {
      json[r'data'] = null;
    }
      json[r'detail'] = this.detail;
    if (this.requestId != null) {
      json[r'request_id'] = this.requestId;
    } else {
      json[r'request_id'] = null;
    }
    if (this.retryAfterS != null) {
      json[r'retry_after_s'] = this.retryAfterS;
    } else {
      json[r'retry_after_s'] = null;
    }
    if (this.status != null) {
      json[r'status'] = this.status;
    } else {
      json[r'status'] = null;
    }
    return json;
  }

  /// Returns a new [ErrorEnvelope] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static ErrorEnvelope? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        assert(json.containsKey(r'detail'), 'Required key "ErrorEnvelope[detail]" is missing from JSON.');
        assert(json[r'detail'] != null, 'Required key "ErrorEnvelope[detail]" has a null value in JSON.');
        return true;
      }());

      return ErrorEnvelope(
        code: mapValueOfType<String>(json, r'code'),
        data: mapValueOfType<Object>(json, r'data'),
        detail: mapValueOfType<String>(json, r'detail')!,
        requestId: mapValueOfType<String>(json, r'request_id'),
        retryAfterS: mapValueOfType<int>(json, r'retry_after_s'),
        status: mapValueOfType<int>(json, r'status'),
      );
    }
    return null;
  }

  static List<ErrorEnvelope> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <ErrorEnvelope>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = ErrorEnvelope.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, ErrorEnvelope> mapFromJson(dynamic json) {
    final map = <String, ErrorEnvelope>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = ErrorEnvelope.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of ErrorEnvelope-objects as value to a dart map
  static Map<String, List<ErrorEnvelope>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<ErrorEnvelope>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = ErrorEnvelope.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'detail',
  };
}

