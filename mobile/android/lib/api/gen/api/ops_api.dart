//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;


class OpsApi {
  OpsApi([ApiClient? apiClient]) : apiClient = apiClient ?? defaultApiClient;

  final ApiClient apiClient;

  /// Operations after a sequence number (5.7); long-polls up to wait_s (≤ 25).
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [int] after:
  ///
  /// * [int] limit:
  ///
  /// * [num] waitS:
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> opsPullWithHttpInfo(String projectId, { int? after, int? limit, num? waitS, String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/projects/{project_id}/ops'
      .replaceAll('{project_id}', projectId);

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (after != null) {
      queryParams.addAll(_queryParams('', 'after', after));
    }
    if (limit != null) {
      queryParams.addAll(_queryParams('', 'limit', limit));
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

  /// Operations after a sequence number (5.7); long-polls up to wait_s (≤ 25).
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [int] after:
  ///
  /// * [int] limit:
  ///
  /// * [num] waitS:
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<PullPage?> opsPull(String projectId, { int? after, int? limit, num? waitS, String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await opsPullWithHttpInfo(projectId, after: after, limit: limit, waitS: waitS, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'PullPage',) as PullPage;
    
    }
    return null;
  }

  /// Push operations (5.6), at most 200; each answers accepted, duplicate, rejected or not_processed (§6.3).
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [PushIn] pushIn (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> opsPushWithHttpInfo(String projectId, PushIn pushIn, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/projects/{project_id}/ops'
      .replaceAll('{project_id}', projectId);

    // ignore: prefer_final_locals
    Object? postBody = pushIn;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (xTruebexContract != null) {
      headerParams[r'X-Truebex-Contract'] = parameterToString(xTruebexContract);
    }

    const contentTypes = <String>['application/json'];


    return apiClient.invokeAPI(
      path,
      'POST',
      queryParams,
      postBody,
      headerParams,
      formParams,
      contentTypes.isEmpty ? null : contentTypes.first,
      abortTrigger: abortTrigger,
    );
  }

  /// Push operations (5.6), at most 200; each answers accepted, duplicate, rejected or not_processed (§6.3).
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [PushIn] pushIn (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<PushAnswer?> opsPush(String projectId, PushIn pushIn, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await opsPushWithHttpInfo(projectId, pushIn, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'PushAnswer',) as PushAnswer;
    
    }
    return null;
  }
}
