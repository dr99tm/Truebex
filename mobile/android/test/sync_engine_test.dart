// The human test's seed, headless: edit offline, reconnect, and the background
// sync sends it (accepted, no notification); a conflicting offline edit comes
// back rejected with a notification naming who won; a lapsed Google session is
// renewed silently; a starred project's tiles are prefetched on an unmetered
// network; an unshared project leaves the phone.

import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:truebex/actions/actions.dart';
import 'package:truebex/actions/finishes.dart';
import 'package:truebex/auth/session.dart';
import 'package:truebex/outbox/outbox.dart';
import 'package:truebex/project/project_controller.dart';
import 'package:truebex/screens/panels.dart';
import 'package:truebex/sync/background.dart';
import 'package:truebex/sync/sync_engine.dart';

import 'helpers.dart';

const pid = 'a0000000000000000000000000000001';
const kitchenWall = '0199c6a2e00070018000000000000004';

void main() {
  late FakeLog log;
  late SilentNotifier notices;
  late NoScheduler scheduler;

  setUp(() {
    log = FakeLog(projectId: pid);
    notices = SilentNotifier();
    scheduler = NoScheduler();
  });

  Future<ProjectController> openOffline(dynamic services) async {
    // The app opened the project once online (record, log), then the network went.
    await services.engine.syncProject(pid);
    log.online = false;
    final c = ProjectController(services, pid, connectivity: const Stream.empty());
    await c.start();
    expect(c.offline, isTrue);
    expect(c.status, ProjectStatus.ready);
    return c;
  }

  EditRequest wallEdit() => EditRequest(
        name: 'Wall finish',
        label: 'Wall finish: Sage green (Kitchen, North wall)',
        subject: kitchenWall,
        call: fillFace(kitchenWall, 'left', wallFinishes[1].finish),
      );

  test('an edit made offline goes out when the network returns, without the app', () async {
    final services = await testServices(log, notifier: notices, scheduler: scheduler);
    await services.auth.signInWithPassword('alex@example.com', 'password123');
    for (final o in remoteOps()) {
      log.append(o, replica: o['replica_id'] as String);
    }
    final c = await openOffline(services);
    expect((await services.replica.project(pid))!.pulledSeq, 12);

    await c.edit(wallEdit());
    expect(scheduler.onlineRequests, 1, reason: 'the one-off job is queued for when the network returns');
    final pending = c.entries.single;
    expect(pending.state, EntryState.pending);
    expect(entryState(services.strings, c, pending), 'Waiting for connection');
    expect(pending.op['base_seq'], 12);
    expect(pending.op['touched'], [kitchenWall]);
    c.dispose(); // the app is closed

    // Wi-Fi is back: WorkManager runs the job (truebex.sync.now).
    log.online = true;
    final report = await services.engine.syncAll();
    expect(report.retry, isFalse);
    expect(report.pushed, 1);
    expect(log.ops.last['op_id'], pending.opId);
    expect(log.ops.last['kind'], 'action');
    expect((log.ops.last['action'] as Map)['tool'], 'fill');
    final saved = (await services.replica.get(pending.opId))!;
    expect(saved.state, EntryState.accepted);
    expect(saved.serverSeq, 13);
    expect(notices.shown, isEmpty, reason: 'an accepted edit makes no notification');
    // The history shows it accepted: the log's operation 13, by this person.
    final history = await services.replica.history(pid, me: alexAuthor);
    expect(history.first.serverSeq, 13);
    expect(history.first.mine, isTrue);
    expect((await services.replica.project(pid))!.pulledSeq, 13);
  });

  test('a conflicting offline edit is rejected on reconnect and named in a notification', () async {
    final services = await testServices(log, notifier: notices, scheduler: scheduler);
    await services.auth.signInWithPassword('alex@example.com', 'password123');
    final c = await openOffline(services);
    await c.edit(wallEdit());
    final mine = c.entries.single;
    c.dispose();

    // Meanwhile Sam changes the same wall on the desktop.
    log.append({'op_id': 'f0000000000000000000000000000009', 'author': samAuthor, 'author_kind': 'person',
      'at': '2026-10-09T11:00:00.000Z', 'touched': [kitchenWall], 'kind': 'delta', 'name': 'Wall finish', 'base_seq': 0,
      'delta': 'VEJYRA==', 'delta_format': 'o5/38'});
    log.online = true;
    final report = await services.engine.syncAll();
    expect(report.rejected, 1);
    expect(notices.shown, ['Wall finish: Sage green (Kitchen, North wall): Sam changed this first — your edit was replaced']);
    final rejected = (await services.replica.get(mine.opId))!;
    expect(rejected.state, EntryState.rejected);
    expect(rejected.winning.single.author, samAuthor);
    final history = await services.replica.history(pid, me: alexAuthor);
    expect(history.first.entry?.state, EntryState.rejected);
    expect(history.any((h) => h.serverSeq == 1 && h.author == samAuthor), isTrue);

    // Never sent again, never notified twice.
    final pushes = log.pushes;
    await services.engine.syncAll();
    expect(log.pushes, pushes);
    expect(notices.shown, hasLength(1));
  });

  test('a winner with the person\'s own author id reads "on another device"', () async {
    final services = await testServices(log, notifier: notices, scheduler: scheduler);
    await services.auth.signInWithPassword('alex@example.com', 'password123');
    final c = await openOffline(services);
    await c.edit(wallEdit());
    c.dispose();
    log.append({'op_id': 'f0000000000000000000000000000010', 'author': alexAuthor, 'author_kind': 'person',
      'at': '2026-10-09T11:00:00.000Z', 'touched': [kitchenWall], 'kind': 'action', 'name': 'Wall finish', 'base_seq': 0},
      replica: 'f1000000000000000000000000000001');
    log.online = true;
    await services.engine.syncAll();
    expect(notices.shown.single, endsWith('You changed this first on another device — your edit was replaced'));
  });

  test('a lapsed Google session is renewed silently; a password one signs out', () async {
    final google = FakeGoogle(token: 'google-id-token-for-web-client', silentToken: 'google-id-token-silent');
    final services = await testServices(log, notifier: notices, scheduler: scheduler, google: google);
    expect(await services.auth.signInWithGoogle(), isTrue);
    expect(services.session.method, SignInMethod.google);
    // 24 h later the server no longer takes the token.
    log.token = 'token-2';
    final report = await services.engine.syncAll();
    expect(report.signedOut, isFalse);
    expect(google.silentCalls, 1);
    expect(services.session.token, 'token-2');

    final otherLog = FakeLog(projectId: pid)..token = 'elsewhere';
    final lapsed = await testServices(otherLog, scheduler: scheduler);
    await lapsed.session.save('token-1', SignInMethod.password, 'alex@example.com');
    final r = await lapsed.engine.syncAll();
    expect(r.signedOut, isTrue);
    expect(lapsed.session.token, isNull);
  });

  test('a starred project keeps its panorama offline (tiles prefetched on an unmetered network)', () async {
    log.follow();
    final services = await testServices(log, notifier: notices, scheduler: scheduler);
    await services.auth.signInWithPassword('alex@example.com', 'password123');
    await services.engine.syncAll();
    await services.engine.syncProject(pid);
    await services.replica.setStarred(pid, true);
    final report = await services.engine.syncAll(unmetered: true);
    final m = (await services.replica.manifest(pid, FakeLog.setId))!.manifest!;
    final want = manifestTiles(m, services.engine.needPx).toSet();
    expect(want, hasLength(24));
    expect(report.tilesFetched, 24);
    for (final sha in want) {
      expect(await services.tiles.has(sha), isTrue);
    }
    // Nothing fetched twice; a metered network fetches nothing.
    final asked = log.tileRequests.length;
    await services.engine.syncAll();
    expect(log.tileRequests.length, asked);
  });

  test('a project no longer shared leaves the phone', () async {
    final services = await testServices(log, notifier: notices, scheduler: scheduler);
    await services.auth.signInWithPassword('alex@example.com', 'password123');
    await services.engine.syncProject(pid);
    expect(await services.replica.project(pid), isNotNull);
    log.shared = false;
    await services.engine.syncAll();
    expect(await services.replica.project(pid), isNull);
  });

  test('signing out wipes the replica, the tiles and the token', () async {
    log.follow();
    final services = await testServices(log, notifier: notices, scheduler: scheduler);
    await services.auth.signInWithPassword('alex@example.com', 'password123');
    await services.engine.syncProject(pid);
    await services.replica.setStarred(pid, true);
    await services.engine.syncAll(unmetered: true);
    expect(await services.tiles.size(), greaterThan(0));
    await services.auth.signOut();
    expect(services.session.token, isNull);
    expect(await services.replica.projects(), isEmpty);
    expect(await services.tiles.size(), 0);
    expect(await services.replica.json('me'), isNull);
  });

  test('presence goes out as an Android client', () async {
    final services = await testServices(log, notifier: notices, scheduler: scheduler);
    await services.auth.signInWithPassword('alex@example.com', 'password123');
    final c = ProjectController(services, pid, connectivity: const Stream.empty());
    expect(c.presenceBody().client, 'android');
    await c.start();
    await Future<void>.delayed(const Duration(milliseconds: 100));
    expect(log.presence.first['client'], 'android');
    expect(log.presence.first['replica_id'], await services.session.replicaId(pid));
    c.dispose();
    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(log.presence.last['leaving'], isTrue);
  });
}
