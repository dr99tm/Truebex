// Everything the app and its background jobs share, opened once per isolate.

import 'dart:io';
import 'dart:ui';

import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import 'api/api.dart';
import 'auth/auth_service.dart';
import 'auth/session.dart';
import 'config.dart';
import 'l10n/app_localizations.dart';
import 'outbox/outbox.dart';
import 'replica/database.dart';
import 'replica/replica.dart';
import 'sync/background.dart';
import 'sync/sync_engine.dart';
import 'viewer/tile_cache.dart';
import 'viewer/tile_server.dart';

class Services {
  Services({
    required this.db,
    required this.session,
    required this.api,
    required this.replica,
    required this.outbox,
    required this.tiles,
    required this.tileServer,
    required this.engine,
    required this.auth,
    required this.scheduler,
    required this.strings,
    this.notifier,
  });

  final ReplicaDb db;
  final Session session;
  final TruebexApi api;
  final Replica replica;
  final Outbox outbox;
  final TileCache tiles;
  final TileServer tileServer;
  final SyncEngine engine;
  final AuthService auth;
  final SyncScheduler scheduler;
  final S strings;
  final LocalNotifier? notifier;

  /// The app's own (or, with `background`, a WorkManager job's) services.
  static Future<Services> open({bool background = false}) async {
    final strings = lookupS(const Locale('en'));
    final db = ReplicaDb.open();
    final session = Session(KeystoreSecrets());
    await session.load();
    final api = TruebexApi(base: Uri.parse(Config.api), token: () => session.token);
    final replica = Replica(db);
    final outbox = Outbox(replica);
    final support = await getApplicationSupportDirectory();
    final tiles = TileCache(Directory(p.join(support.path, 'tiles')), db, budgetBytes: Config.tileBudgetBytes);
    final scheduler = WorkScheduler();
    final notifier = LocalNotifier(strings);
    late final AuthService auth;
    final engine = SyncEngine(
      api: api,
      replica: replica,
      session: session,
      outbox: outbox,
      tiles: tiles,
      notifier: notifier,
      text: conflictText(strings),
      reauth: () => auth.renewSilently(),
    );
    final viewerNeed = int.tryParse(await db.getValue('viewer.need_px') ?? '');
    if (viewerNeed != null) engine.needPx = viewerNeed;
    auth = AuthService(
      api: api,
      session: session,
      replica: replica,
      tiles: tiles,
      google: CredentialManagerGoogle(),
      onSignedIn: background ? null : scheduler.start,
      onSignedOut: background
          ? null
          : () async {
              await scheduler.stop();
              await notifier.clear();
            },
    );
    final tileServer = TileServer(
      cache: tiles,
      fetch: (url) => api.fetchBytes(url),
      assets: (name) async {
        try {
          final data = await rootBundle.load('assets/viewer/$name');
          return data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
        } catch (_) {
          return null;
        }
      },
    );
    return Services(
      db: db,
      session: session,
      api: api,
      replica: replica,
      outbox: outbox,
      tiles: tiles,
      tileServer: tileServer,
      engine: engine,
      auth: auth,
      scheduler: scheduler,
      strings: strings,
      notifier: notifier,
    );
  }

  Future<void> close() async {
    await tileServer.stop();
    api.close();
    await db.close();
  }
}

ConflictText conflictText(S s) => ConflictText(named: s.conflict, self: s.conflictSelf, someone: s.someone);
