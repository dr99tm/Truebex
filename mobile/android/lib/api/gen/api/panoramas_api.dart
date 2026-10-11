//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;


class PanoramasApi {
  PanoramasApi([ApiClient? apiClient]) : apiClient = apiClient ?? defaultApiClient;

  final ApiClient apiClient;

  /// One set's newest tile manifest; with `rev` and `wait_s`, held until it moves past `rev`.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [String] setId (required):
  ///
  /// * [int] rev:
  ///
  /// * [num] waitS:
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> panoramasGetWithHttpInfo(String projectId, String setId, { int? rev, num? waitS, String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/projects/{project_id}/panoramas/{set_id}'
      .replaceAll('{project_id}', projectId)
      .replaceAll('{set_id}', setId);

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (rev != null) {
      queryParams.addAll(_queryParams('', 'rev', rev));
    }
    if (waitS != null) {
      queryParams.addAll(_queryParams('', 'wait_s', waitS));
    }

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

  /// One set's newest tile manifest; with `rev` and `wait_s`, held until it moves past `rev`.
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [String] setId (required):
  ///
  /// * [int] rev:
  ///
  /// * [num] waitS:
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<SetState?> panoramasGet(String projectId, String setId, { int? rev, num? waitS, String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await panoramasGetWithHttpInfo(projectId, setId, rev: rev, waitS: waitS, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'SetState',) as SetState;
    
    }
    return null;
  }

  /// The project's followed panorama sets (members' read).
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> panoramasListWithHttpInfo(String projectId, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/projects/{project_id}/panoramas'
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

  /// The project's followed panorama sets (members' read).
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<PanoramaSets?> panoramasList(String projectId, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await panoramasListWithHttpInfo(projectId, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'PanoramaSets',) as PanoramaSets;
    
    }
    return null;
  }
}
