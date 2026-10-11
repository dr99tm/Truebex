//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;


class PresenceApi {
  PresenceApi([ApiClient? apiClient]) : apiClient = apiClient ?? defaultApiClient;

  final ApiClient apiClient;

  /// Who is in the project (5.18).
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> presenceGetWithHttpInfo(String projectId, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/projects/{project_id}/presence'
      .replaceAll('{project_id}', projectId);

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (xTruebexContract != null) {
      headerParams[r'X-Truebex-Contract'] = parameterToString(xTruebexContract);
    }

    const contentTypes = <String>[];


    return apiClient.invokeAPI(
      path,
      'GET',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
      abortTrigger: abortTrigger,
    );
  }

  /// Who is in the project (5.18).
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<PresenceList?> presenceGet(String projectId, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await presenceGetWithHttpInfo(projectId, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'PresenceList',) as PresenceList;
    
    }
    return null;
  }

  /// Heartbeat (5.17) with the client kind and view; `leaving` removes it.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [PresenceIn] presenceIn (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> presencePutWithHttpInfo(String projectId, PresenceIn presenceIn, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/projects/{project_id}/presence'
      .replaceAll('{project_id}', projectId);

    // ignore: prefer_final_locals
    Object? postBody = presenceIn;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (xTruebexContract != null) {
      headerParams[r'X-Truebex-Contract'] = parameterToString(xTruebexContract);
    }

    const contentTypes = <String>['application/json'];


    return apiClient.invokeAPI(
      path,
      'PUT',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
      abortTrigger: abortTrigger,
    );
  }

  /// Heartbeat (5.17) with the client kind and view; `leaving` removes it.
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [PresenceIn] presenceIn (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<PresenceAnswer?> presencePut(String projectId, PresenceIn presenceIn, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await presencePutWithHttpInfo(projectId, presenceIn, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'PresenceAnswer',) as PresenceAnswer;
    
    }
    return null;
  }
}
