// Shared by the Flutter tests: the contract fixtures (the same files PF9's
// self-test and the platform's pytest read), an in-memory replica, and a
// stand-in project-log server that applies contract §6.3 for push and pull.

import 'dart:convert';
import 'dart:io';

import 'package:drift/drift.dart' show driftRuntimeOptions;
import 'package:drift/native.dart';
import 'package:flutter/widgets.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:truebex/api/api.dart';
import 'package:truebex/auth/auth_service.dart';
import 'package:truebex/auth/session.dart';
import 'package:truebex/l10n/app_localizations.dart';
import 'package:truebex/outbox/outbox.dart';
import 'package:truebex/replica/database.dart';
import 'package:truebex/replica/replica.dart';
import 'package:truebex/services.dart';
import 'package:truebex/sync/background.dart';
import 'package:truebex/sync/sync_engine.dart';
import 'package:truebex/viewer/tile_cache.dart';
import 'package:truebex/viewer/tile_server.dart';

/// The project-log contract fixtures: `server/tests/contracts/project-log/` (tests run in mobile/android).
const fixtureDir = '../../server/tests/contracts/project-log';

Map<String, Object?> fixture(String name) =>
    (jsonDecode(File('$fixtureDir/$name').readAsStringSync()) as Map).cast<String, Object?>();

ReplicaDb memoryDb() {
  // Every test opens its own in-memory database on purpose.
  driftRuntimeOptions.dontWarnAboutMultipleDatabases = true;
  return ReplicaDb(NativeDatabase.memory());
}

// The author ids of the fixture's members (members.json, project-log 1.1.0): Ana the owner, Sam the editor.
const alexAuthor = '019a2b3c4d5e7000a000000000000042';
const samAuthor = '019a2b3c4d5e7000a000000000000007';
const samDesktop = 'b0000000000000000000000000000002';

/// A project-log server in memory: one project, §6.3 order and conflicts, pages of `limit`.
class FakeLog {
  FakeLog({this.projectId = 'a0000000000000000000000000000001', this.role = 'editor'});

  final String projectId;
  String role;
  final List<Map<String, Object?>> ops = [];
  bool online = true;
  int pushes = 0;
  int pulls = 0;
  final List<List<String>> pushedIds = [];
  int statusOverride = 0;
  String? retryAfter;
  String token = 'token-1';
  bool shared = true;

  /// A followed panorama set (render-jobs' manifest-panorama.json) and its tiles, once `follow()`ed.
  static const setId = 'c1000000000000000000000000000001';
  Map<String, Object?>? manifest;
  int setRev = 0;
  final List<String> tileRequests = [];

  /// The heartbeats (5.17) the app sent.
  final List<Map<String, Object?>> presence = [];

  void follow() {
    manifest = renderManifest();
    setRev++;
  }

  int get head => ops.length;

  /// Operations another replica wrote (Sam's desktop app).
  void append(Map<String, Object?> op, {String replica = samDesktop}) {
    ops.add({'delta': null, 'delta_format': null, 'action': null, 'restore': null, ...op, 'server_seq': ops.length + 1, 'replica_id': replica});
  }

  Map<String, Object?> push(String replica, List<Map<String, Object?>> batch) {
    pushedIds.add([for (final o in batch) o['op_id'] as String]);
    final results = <Map<String, Object?>>[];
    var stopped = false;
    for (final op in batch) {
      if (stopped) {
        results.add({'op_id': op['op_id'], 'status': 'not_processed'});
        continue;
      }
      final stored = ops.where((o) => o['op_id'] == op['op_id']).firstOrNull;
      if (stored != null) {
        results.add({'op_id': op['op_id'], 'status': 'duplicate', 'server_seq': stored['server_seq']});
        continue;
      }
      final touched = (op['touched'] as List).toSet();
      final base = op['base_seq'] as int;
      final winning = ops
          .where((w) => w['replica_id'] != replica && (w['server_seq'] as int) > base && (w['touched'] as List).any(touched.contains))
          .toList();
      if (winning.isNotEmpty) {
        results.add({'op_id': op['op_id'], 'status': 'rejected', 'reason': 'conflict', 'winning': winning, 'more': false});
        stopped = true;
        continue;
      }
      ops.add({...op, 'server_seq': ops.length + 1, 'replica_id': replica, 'delta': null, 'delta_format': null, 'restore': null});
      results.add({'op_id': op['op_id'], 'status': 'accepted', 'server_seq': ops.length});
    }
    return {'head_seq': head, 'results': results};
  }

  Map<String, Object?> record({bool list = false}) => {
        'project_id': projectId,
        'name': 'House',
        'role': role,
        'owner': {'user_id': 42, 'name': 'Alex'},
        'org_id': null,
        'created_at': '2026-10-09T10:00:00Z',
        'updated_at': '2026-10-09T10:00:00Z',
        'head_seq': head,
        'latest_snapshot': null,
        'doc_version': 38,
        'members': list
            ? 2
            : [
                {'user_id': 42, 'invite_id': null, 'email': 'alex@example.com', 'name': 'Alex', 'role': 'owner', 'state': 'active',
                  'invited_at': null, 'accepted_at': null, 'author_id': alexAuthor},
                {'user_id': 7, 'invite_id': null, 'email': 'sam@example.com', 'name': 'Sam', 'role': 'editor', 'state': 'active',
                  'invited_at': null, 'accepted_at': null, 'author_id': samAuthor},
              ],
        'bytes': 0,
        if (!list) 'quota': {'bytes': null, 'bytes_used': 0},
      };

  static const _me = {
    'id': 42, 'email': 'alex@example.com', 'created_at': '2026-10-09T10:00:00Z', 'plan': 'pro', 'name': 'Alex',
    'has_password': true, 'google_linked': false, 'is_admin': false, 'author_id': alexAuthor,
  };

  http.Response _json(Object body, [int status = 200, Map<String, String> headers = const {}]) =>
      http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json', ...headers});

  /// The routes the app calls, enough for the sync engine and the screens.
  MockClient client() => MockClient((req) async {
        if (!online) throw const SocketException('offline');
        final path = req.url.path;
        if (req.url.host == 'tiles.test') {
          final sha = path.split('/').last.replaceAll('.jpg', '');
          tileRequests.add(sha);
          final f = File('$renderDir/tiles/$sha.jpg');
          return f.existsSync() ? http.Response.bytes(f.readAsBytesSync(), 200) : http.Response('', 404);
        }
        if (statusOverride != 0 && path.contains('/ops')) {
          final s = statusOverride;
          return _json({'detail': 'busy', 'code': 'unavailable', 'status': s, 'retry_after_s': 7}, s,
              {'retry-after': ?retryAfter});
        }
        if (path == '/auth/login' || path == '/auth/google') {
          return _json({'access_token': token, 'token_type': 'bearer', 'user': _me});
        }
        final auth = req.headers['Authorization'] ?? req.headers['authorization'];
        if (!path.startsWith('/market') && auth != 'Bearer $token') {
          return _json({'detail': 'Not signed in.', 'code': 'unauthenticated', 'status': 401}, 401);
        }
        final p = '/projects/$projectId';
        if (path == '/auth/me') return _json(_me);
        if (path == '/projects') return _json({'projects': [if (shared) record(list: true)], 'next_cursor': null});
        if (!shared && path.startsWith(p)) return _json({'detail': 'gone', 'code': 'not_found', 'status': 404}, 404);
        if (path == p) return _json(record());
        if (path == '$p/ops' && req.method == 'POST') {
          pushes++;
          final body = jsonDecode(req.body) as Map;
          final batch = [for (final o in body['ops'] as List) (o as Map).cast<String, Object?>()];
          return _json(push(body['replica_id'] as String, batch));
        }
        if (path == '$p/ops') {
          pulls++;
          final after = int.parse(req.url.queryParameters['after'] ?? '0');
          final limit = int.parse(req.url.queryParameters['limit'] ?? '1000');
          final rest = ops.where((o) => (o['server_seq'] as int) > after).toList();
          return _json({'ops': rest.take(limit).toList(), 'head_seq': head, 'more': rest.length > limit});
        }
        if (path == '$p/snapshots/latest') return _json({'detail': 'none', 'code': 'not_found', 'status': 404}, 404);
        if (path == '$p/panoramas') {
          return _json({'sets': [
            if (manifest != null)
              {'set_id': setId, 'rev': setRev, 'at_seq': 0, 'views': [for (final v in manifest!['views'] as List) (v as Map)['view']],
                'following': true, 'mine': true, 'updated_at': '2026-10-09T10:00:00Z'},
          ]});
        }
        if (path == '$p/panoramas/$setId' && manifest != null) {
          return _json({'rev': setRev, 'job_id': 'c2000000000000000000000000000001', 'follow_job_id': setId, 'at_seq': 0,
            'following': true, 'manifest': manifest});
        }
        if (path == '$p/presence') {
          if (req.method == 'PUT') presence.add((jsonDecode(req.body) as Map).cast<String, Object?>());
          return _json({'ttl_s': 30, 'others': []});
        }
        return _json({'detail': 'no route $path', 'code': 'not_found', 'status': 404}, 404);
      });
}

const renderDir = '../../server/tests/contracts/render-jobs';

/// PF6's fixture manifest, served from the stand-in tiles host.
Map<String, Object?> renderManifest() {
  final m = (jsonDecode(File('$renderDir/manifest-panorama.json').readAsStringSync()) as Map).cast<String, Object?>();
  return {...m, 'tiles_base': 'https://tiles.test/t'};
}

/// The operations of ops-remote.json as the server answers them (numbered from 1, every
/// §6.2 key present). CL1's file names each operation's own replica_id.
List<Map<String, Object?>> remoteOps() {
  final body = fixture('ops-remote.json');
  var seq = 0;
  return [
    for (final o in body['ops'] as List) {'action': null, 'restore': null, ...(o as Map).cast<String, Object?>(), 'server_seq': ++seq},
  ];
}

/// A Google account picker that answers with a fixed ID token (or none).
class FakeGoogle implements GoogleTokens {
  FakeGoogle({this.token, this.silentToken});
  String? token;
  String? silentToken;
  int silentCalls = 0;

  @override
  bool get available => true;

  @override
  Future<String?> idToken({required bool silent}) async {
    if (silent) {
      silentCalls++;
      return silentToken;
    }
    return token;
  }

  @override
  Future<void> signOut() async {}
}

/// The app's services wired to the stand-in server, an in-memory replica and a temp tile folder.
Future<Services> testServices(FakeLog log, {SilentNotifier? notifier, FakeGoogle? google, NoScheduler? scheduler, TileFetch? fetchTile}) async {
  final strings = lookupS(const Locale('en'));
  final db = memoryDb();
  final session = Session(MemorySecrets());
  final api = TruebexApi(base: Uri.parse('https://api.test'), client: log.client(), token: () => session.token);
  final replica = Replica(db);
  final outbox = Outbox(replica);
  final dir = await Directory.systemTemp.createTemp('truebex-tiles');
  final tiles = TileCache(dir, db);
  late final AuthService auth;
  final engine = SyncEngine(
    api: api,
    replica: replica,
    session: session,
    outbox: outbox,
    tiles: tiles,
    notifier: notifier ?? SilentNotifier(),
    text: conflictText(strings),
    reauth: () => auth.renewSilently(),
  );
  auth = AuthService(api: api, session: session, replica: replica, tiles: tiles, google: google ?? FakeGoogle());
  final server = TileServer(
    cache: tiles,
    fetch: fetchTile ?? (url) => api.fetchBytes(url),
    assets: (name) async {
      final f = File('assets/viewer/$name');
      return f.existsSync() ? f.readAsBytesSync() : null;
    },
  );
  return Services(
    db: db,
    session: session,
    api: api,
    replica: replica,
    outbox: outbox,
    tiles: tiles,
    tileServer: server,
    engine: engine,
    auth: auth,
    scheduler: scheduler ?? NoScheduler(),
    strings: strings,
  );
}
