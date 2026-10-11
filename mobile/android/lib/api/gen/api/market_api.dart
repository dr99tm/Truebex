//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of truebex.api;


class MarketApi {
  MarketApi([ApiClient? apiClient]) : apiClient = apiClient ?? defaultApiClient;

  final ApiClient apiClient;

  /// Prices and availability of the placed products for a region (5.5).
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [PricesRequest] pricesRequest (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> marketPricesWithHttpInfo(PricesRequest pricesRequest, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/market/prices';

    // ignore: prefer_final_locals
    Object? postBody = pricesRequest;

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

  /// Prices and availability of the placed products for a region (5.5).
  ///
  /// Parameters:
  ///
  /// * [PricesRequest] pricesRequest (required):
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<PricesAnswer?> marketPrices(PricesRequest pricesRequest, { String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await marketPricesWithHttpInfo(pricesRequest, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'PricesAnswer',) as PricesAnswer;
    
    }
    return null;
  }

  /// One product with its variants and the region's prices (5.4).
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] productId (required):
  ///
  /// * [String] region:
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> marketProductWithHttpInfo(String productId, { String? region, String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/market/products/{product_id}'
      .replaceAll('{product_id}', productId);

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (region != null) {
      queryParams.addAll(_queryParams('', 'region', region));
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

  /// One product with its variants and the region's prices (5.4).
  ///
  /// Parameters:
  ///
  /// * [String] productId (required):
  ///
  /// * [String] region:
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<ProductAnswer?> marketProduct(String productId, { String? region, String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await marketProductWithHttpInfo(productId, region: region, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'ProductAnswer',) as ProductAnswer;
    
    }
    return null;
  }

  /// Products by category and region (5.3), for a swap.
  ///
  /// Note: This method returns the HTTP [Response].
  ///
  /// Parameters:
  ///
  /// * [String] q:
  ///
  /// * [String] category:
  ///
  /// * [String] region:
  ///
  /// * [int] min:
  ///
  /// * [int] max:
  ///
  /// * [bool] available:
  ///
  /// * [String] supplier:
  ///
  /// * [String] kind:
  ///
  /// * [String] sort:
  ///
  /// * [String] cursor:
  ///
  /// * [int] limit:
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<Response> marketSearchWithHttpInfo({ String? q, String? category, String? region, int? min, int? max, bool? available, String? supplier, String? kind, String? sort, String? cursor, int? limit, String? xTruebexContract, Future<void>? abortTrigger, }) async {
    // ignore: prefer_const_declarations
    final path = r'/market/search';

    // ignore: prefer_final_locals
    Object? postBody;

    final queryParams = <QueryParam>[];
    final headerParams = <String, String>{};
    final formParams = <String, String>{};

    if (q != null) {
      queryParams.addAll(_queryParams('', 'q', q));
    }
    if (category != null) {
      queryParams.addAll(_queryParams('', 'category', category));
    }
    if (region != null) {
      queryParams.addAll(_queryParams('', 'region', region));
    }
    if (min != null) {
      queryParams.addAll(_queryParams('', 'min', min));
    }
    if (max != null) {
      queryParams.addAll(_queryParams('', 'max', max));
    }
    if (available != null) {
      queryParams.addAll(_queryParams('', 'available', available));
    }
    if (supplier != null) {
      queryParams.addAll(_queryParams('', 'supplier', supplier));
    }
    if (kind != null) {
      queryParams.addAll(_queryParams('', 'kind', kind));
    }
    if (sort != null) {
      queryParams.addAll(_queryParams('', 'sort', sort));
    }
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

  /// Products by category and region (5.3), for a swap.
  ///
  /// Parameters:
  ///
  /// * [String] q:
  ///
  /// * [String] category:
  ///
  /// * [String] region:
  ///
  /// * [int] min:
  ///
  /// * [int] max:
  ///
  /// * [bool] available:
  ///
  /// * [String] supplier:
  ///
  /// * [String] kind:
  ///
  /// * [String] sort:
  ///
  /// * [String] cursor:
  ///
  /// * [int] limit:
  ///
  /// * [String] xTruebexContract:
  ///   The contract and version the client speaks; a MAJOR the server does not serve is 400 `contract_version`.
  Future<SearchAnswer?> marketSearch({ String? q, String? category, String? region, int? min, int? max, bool? available, String? supplier, String? kind, String? sort, String? cursor, int? limit, String? xTruebexContract, Future<void>? abortTrigger, }) async {
    final response = await marketSearchWithHttpInfo(q: q, category: category, region: region, min: min, max: max, available: available, supplier: supplier, kind: kind, sort: sort, cursor: cursor, limit: limit, xTruebexContract: xTruebexContract, abortTrigger: abortTrigger,);
    if (response.statusCode >= HttpStatus.badRequest) {
      throw ApiException(response.statusCode, await _decodeBodyBytes(response));
    }
    // When a remote server returns no body with a status of 204, we shall not decode it.
    // At the time of writing this, `dart:convert` will throw an "Unexpected end of input"
    // FormatException when trying to decode an empty string.
    if (response.body.isNotEmpty && response.statusCode != HttpStatus.noContent) {
      return await apiClient.deserializeAsync(await _decodeBodyBytes(response), 'SearchAnswer',) as SearchAnswer;
    
    }
    return null;
  }
}
