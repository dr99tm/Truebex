//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;


class ProjectsApi {
  ProjectsApi([ApiClient? apiClient]) : apiClient = apiClient ?? defaultApiClient;

  final ApiClient apiClient;

  /// Projects I own or that are shared with me (5.2), newest activity first.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] cursor:
  ///
  /// * [int] limit:
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> projectsListWithHttpInfo({ String? cursor, int? limit, String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/projects';

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (cursor != null) {
      queryParams.addAll(_queryParams('', 'cursor', cursor));
    }
    if (limit != null) {
      queryParams.addAll(_queryParams('', 'limit', limit));
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

  /// Projects I own or that are shared with me (5.2), newest activity first.
  ///
  /// Parameters:
  ///
  /// * [String] cursor:
  ///
  /// * [int] limit:
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<ProjectList?> projectsList({ String? cursor, int? limit, String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await projectsListWithHttpInfo(cursor: cursor, limit: limit, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'ProjectList',) as ProjectList;
    
    }
    return null;
  }

  /// Open a project (5.3): the record, its head, members and quota.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> projectsOpenWithHttpInfo(String projectId, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/projects/{project_id}'
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

  /// Open a project (5.3): the record, its head, members and quota.
  ///
  /// Parameters:
  ///
  /// * [String] projectId (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<OpenProject?> projectsOpen(String projectId, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await projectsOpenWithHttpInfo(projectId, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'OpenProject',) as OpenProject;
    
    }
    return null;
  }
}
