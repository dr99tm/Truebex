// The Android app as a client of the platform: every call goes through the
// Dart client generated from openapi/clients.json (lib/api/gen/, made by
// scripts/gen-clients.ps1 — the document PF9's TypeScript types come from too).
// This file only adds what a generated client cannot know: the session token,
// the contract header each group speaks, the shared error envelope with
// `Retry-After`, and a network failure told apart from a server's answer.

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../sync/backoff.dart';
import 'gen/api.dart';

export 'gen/api.dart';

const logContract = 'project-log/1.0';
const marketContract = 'marketplace-api/1.1';

/// A call that failed: `status` 0 means no answer arrived (offline, timeout).
class ApiFailure implements Exception {
  ApiFailure(this.status, this.code, this.message, {this.retryAfter, this.data});

  final int status;
  final String code;
  final String message;
  final Duration? retryAfter;
  final Map<String, Object?>? data;

  bool get offline => status == 0;
  bool get unauthenticated => status == 401;
  bool get retryable => isRetryable(status);

  @override
  String toString() => 'ApiFailure($status $code: $message)';
}

bool isRetryable(int status) => retryable(status);

/// The answer of a long-poll or a page, with what the client needs besides the body.
class Answer<T> {
  Answer(this.body, this.status);
  final T body;
  final int status;
}

class TruebexApi {
  TruebexApi({required Uri base, http.Client? client, String? Function()? token})
      : _token = token ?? (() => null),
        _http = client ?? http.Client() {
    final auth = HttpBearerAuth()..accessToken = () => _token() ?? '';
    api = ApiClient(basePath: base.toString().replaceAll(RegExp(r'/$'), ''), authentication: auth)..client = _http;
    authApi = AuthApi(api);
    projects = ProjectsApi(api);
    snapshots = SnapshotsApi(api);
    ops = OpsApi(api);
    presence = PresenceApi(api);
    members = MembersApi(api);
    panoramas = PanoramasApi(api);
    market = MarketApi(api);
  }

  final String? Function() _token;
  final http.Client _http;
  late final ApiClient api;
  late final AuthApi authApi;
  late final ProjectsApi projects;
  late final SnapshotsApi snapshots;
  late final OpsApi ops;
  late final PresenceApi presence;
  late final MembersApi members;
  late final PanoramasApi panoramas;
  late final MarketApi market;

  http.Client get httpClient => _http;

  /// Run a generated `…WithHttpInfo` call and decode its answer as `type`.
  Future<T> call<T>(Future<http.Response> Function() send, String type, {Duration? timeout}) async {
    http.Response res;
    try {
      final pending = send();
      res = await (timeout == null ? pending : pending.timeout(timeout));
    } on ApiException catch (e) {
      // The generated client reports a socket or TLS failure as a 400 with the cause inside.
      if (e.innerException != null) throw ApiFailure(0, 'network', e.message ?? 'network');
      throw ApiFailure(e.code, 'http_${e.code}', e.message ?? '');
    } on TimeoutException {
      throw ApiFailure(0, 'timeout', 'timeout');
    } on SocketException catch (e) {
      throw ApiFailure(0, 'network', e.message);
    } on http.ClientException catch (e) {
      throw ApiFailure(0, 'network', e.message);
    } on HandshakeException catch (e) {
      throw ApiFailure(0, 'network', e.message);
    }
    final text = utf8.decode(res.bodyBytes, allowMalformed: true);
    if (res.statusCode >= 400) throw failureOf(res.statusCode, text, res.headers['retry-after']);
    final decoded = await api.deserializeAsync(text, type);
    if (decoded is! T) throw ApiFailure(res.statusCode, 'bad_answer', 'Unexpected answer for $type');
    return decoded;
  }

  /// The shared envelope `{detail, code, status, request_id, retry_after_s, data}` (§7).
  static ApiFailure failureOf(int status, String body, String? retryAfterHeader) {
    Object? json;
    try {
      json = jsonDecode(body);
    } on FormatException {
      json = null;
    }
    final map = json is Map ? json.cast<String, Object?>() : const <String, Object?>{};
    final detail = map['detail'];
    final data = map['data'];
    return ApiFailure(
      status,
      (map['code'] as String?) ?? 'http_$status',
      detail is String ? detail : (detail == null ? 'HTTP $status' : jsonEncode(detail)),
      retryAfter: parseRetryAfter(retryAfterHeader, envelopeSeconds: map['retry_after_s']),
      data: data is Map ? data.cast<String, Object?>() : null,
    );
  }

  // --- account -------------------------------------------------------------------------------

  Future<Token> login(String email, String password) =>
      call(() => authApi.authLoginWithHttpInfo(UserLogin(email: email, password: password)), 'Token');

  Future<Token> google(String idToken) =>
      call(() => authApi.authGoogleWithHttpInfo(GoogleLogin(credential: idToken)), 'Token');

  Future<UserOut> me() => call(() => authApi.authMeWithHttpInfo(), 'UserOut');

  // --- projects and the log ----------------------------------------------------------------

  Future<ProjectList> listProjects({String? cursor}) =>
      call(() => projects.projectsListWithHttpInfo(cursor: cursor, limit: 100, xTruebexContract: logContract), 'ProjectList');

  Future<OpenProject> openProject(String pid) =>
      call(() => projects.projectsOpenWithHttpInfo(pid, xTruebexContract: logContract), 'OpenProject');

  /// 5.9; null before the first snapshot (404 `not_found`).
  Future<Snapshot?> latestSnapshot(String pid) async {
    try {
      return await call(() => snapshots.snapshotsLatestWithHttpInfo(pid, xTruebexContract: logContract), 'Snapshot');
    } on ApiFailure catch (e) {
      if (e.status == 404) return null;
      rethrow;
    }
  }

  /// 5.7: operations after `after`, ≤ `limit`; with `waitS`, held until one arrives.
  Future<PullPage> pull(String pid, int after, {int limit = 1000, int waitS = 0, Future<void>? abort}) => call(
        () => ops.opsPullWithHttpInfo(pid, after: after, limit: limit, waitS: waitS, xTruebexContract: logContract, abortTrigger: abort),
        'PullPage',
        timeout: Duration(seconds: waitS + 30),
      );

  /// 5.6: at most 200 operations, as JSON maps exactly as built.
  Future<PushAnswer> push(String pid, String replicaId, List<Map<String, Object?>> operations) {
    final body = PushIn(replicaId: replicaId, ops: [for (final o in operations) OpIn.fromJson(o)!]);
    return call(() => ops.opsPushWithHttpInfo(pid, body, xTruebexContract: logContract), 'PushAnswer',
        timeout: const Duration(seconds: 60));
  }

  Future<PresenceAnswer> heartbeat(String pid, PresenceIn body) =>
      call(() => presence.presencePutWithHttpInfo(pid, body, xTruebexContract: logContract), 'PresenceAnswer',
          timeout: const Duration(seconds: 20));

  Future<MemberList> listMembers(String pid) =>
      call(() => members.membersListWithHttpInfo(pid, xTruebexContract: logContract), 'MemberList');

  // --- panoramas ------------------------------------------------------------------------------

  Future<PanoramaSets> listSets(String pid) =>
      call(() => panoramas.panoramasListWithHttpInfo(pid, xTruebexContract: logContract), 'PanoramaSets');

  Future<SetState> setState(String pid, String setId, {int? rev, int waitS = 0, Future<void>? abort}) => call(
        () => panoramas.panoramasGetWithHttpInfo(pid, setId, rev: rev, waitS: rev == null ? null : waitS,
            xTruebexContract: logContract, abortTrigger: abort),
        'SetState',
        timeout: Duration(seconds: waitS + 30),
      );

  // --- the marketplace -------------------------------------------------------------------------

  Future<PricesAnswer> prices(String region, List<Map<String, String>> items) => call(
        () => market.marketPricesWithHttpInfo(
          PricesRequest(region: region, items: [for (final i in items) PriceItem(supplierId: i['supplier_id']!, sku: i['sku']!, variantId: i['variant_id']!, qty: 1)]),
          xTruebexContract: marketContract,
        ),
        'PricesAnswer',
      );

  Future<SearchAnswer> search({required String category, String? region, int limit = 6}) => call(
        () => market.marketSearchWithHttpInfo(category: category, region: region, limit: limit, xTruebexContract: marketContract),
        'SearchAnswer',
      );

  Future<ProductAnswer> product(String productId, {String? region}) => call(
        () => market.marketProductWithHttpInfo(productId, region: region, xTruebexContract: marketContract),
        'ProductAnswer',
      );

  // --- files behind signed URLs (no session sent) ------------------------------------------

  /// A signed URL (the digest) or a tile: the storage checks the signature, never the session.
  Future<Uint8List> fetchBytes(Uri url, {Duration timeout = const Duration(seconds: 30)}) async {
    http.Response res;
    try {
      res = await _http.get(url).timeout(timeout);
    } on TimeoutException {
      throw ApiFailure(0, 'timeout', 'timeout');
    } on SocketException catch (e) {
      throw ApiFailure(0, 'network', e.message);
    } on http.ClientException catch (e) {
      throw ApiFailure(0, 'network', e.message);
    } on HandshakeException catch (e) {
      throw ApiFailure(0, 'network', e.message);
    }
    if (res.statusCode >= 400) throw failureOf(res.statusCode, '', res.headers['retry-after']);
    return res.bodyBytes;
  }

  void close() => _http.close();
}
