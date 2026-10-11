// viewer_offline_interception: with the network off, the project screen shows
// the panorama through the app's own server, and every tile request the viewer
// makes is answered from the phone's cache (a tile it never saw answers 504).
// The web view is a stand-in that requests exactly what PF9's viewer would:
// the page, then `<tiles_base>/<sha>.jpg` for each tile of the level it shows.

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:truebex/l10n/app_localizations.dart';
import 'package:truebex/project/project_controller.dart';
import 'package:truebex/screens/project_screen.dart';
import 'package:truebex/services.dart';
import 'package:truebex/sync/sync_engine.dart';
import 'package:truebex/viewer/panorama_view.dart';

import 'helpers.dart';

const pid = 'a0000000000000000000000000000001';

/// The web view's stand-in: records what the app asks of the page.
class FakeSurface implements ViewerSurface {
  Uri? loaded;
  final List<String> scripts = [];
  void Function(String)? _handler;

  /// Each `window.truebex.show(...)` call's arguments (all JSON values).
  List<List<Object?>> get shows => [
        for (final js in scripts)
          if (js.startsWith('window.truebex.show('))
            jsonDecode('[${js.substring('window.truebex.show('.length, js.length - 1)}]') as List<Object?>,
      ];

  void emit(String message) => _handler?.call(message);

  @override
  Future<void> load(Uri url) async => loaded = url;

  @override
  Future<void> run(String javascript) async => scripts.add(javascript);

  @override
  void onMessage(void Function(String message) handler) => _handler = handler;

  @override
  Widget build(BuildContext context) => const ColoredBox(color: Colors.black);
}

Future<({int status, List<int> body})> get(Uri url) async {
  final client = HttpClient();
  try {
    final res = await (await client.getUrl(url)).close();
    final body = await res.fold<List<int>>(<int>[], (all, chunk) => all..addAll(chunk));
    return (status: res.statusCode, body: body);
  } finally {
    client.close(force: true);
  }
}

Widget app(Widget home) => MaterialApp(
      localizationsDelegates: const [S.delegate, GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
      supportedLocales: S.supportedLocales,
      home: home,
    );

void main() {
  testWidgets('viewer_offline_interception', (tester) async {
    late Services services;
    late FakeLog log;
    late ProjectController c;
    late int fetchedOnline;
    await tester.runAsync(() async {
      // flutter_test answers every HttpClient request with 400 unless told otherwise.
      HttpOverrides.global = null;
      log = FakeLog(projectId: pid)..follow();
      services = await testServices(log);
      await services.auth.signInWithPassword('alex@example.com', 'password123');
      // Online once: the project is opened and starred, its tiles kept on the phone.
      await services.engine.syncProject(pid);
      await services.replica.setStarred(pid, true);
      await services.engine.syncAll(unmetered: true);
      fetchedOnline = log.tileRequests.length;
      // Airplane mode.
      log.online = false;
      await services.tileServer.start();
      c = ProjectController(services, pid, connectivity: const Stream.empty());
      await c.start();
    });
    expect(fetchedOnline, 24);
    expect(c.offline, isTrue);

    final surface = FakeSurface();
    await tester.pumpWidget(app(ProjectScreen(services: services, projectId: pid, onSignedOut: () {}, controller: c, surface: (_) => surface)));
    await tester.pump();
    expect(find.byKey(const Key('offlineBanner')), findsOneWidget);
    expect(find.byKey(const Key('panorama')), findsOneWidget);
    expect(find.text('Offline — showing the copy on this phone.'), findsOneWidget);

    // The page comes from the app's own server, not the network.
    expect(surface.loaded, services.tileServer.viewerUrl);
    expect(surface.loaded!.host, '127.0.0.1');
    final page = (await tester.runAsync(() => get(surface.loaded!)))!;
    expect(page.status, 200);
    expect(utf8.decode(page.body), contains('viewer.js'));
    // Another app on the phone cannot read through it without the random path.
    final outside = (await tester.runAsync(() => get(services.tileServer.origin.replace(path: '/viewer/index.html'))))!;
    expect(outside.status, 404);

    // The viewer is ready: the app shows the view with this server as tiles_base.
    surface.emit('{"type":"ready"}');
    await tester.pump();
    final show = surface.shows.single;
    final view = (show[0] as Map).cast<String, Object?>();
    final base = show[1] as String;
    expect(base, services.tileServer.localTilesBase);
    final levels = [for (final l in view['levels'] as List) l as int];
    final level = levelFor(levels, services.engine.needPx);
    final faces = (view['faces'] as Map).cast<String, Object?>();
    final shas = [
      for (final f in faces.values)
        for (final sha in ((f as Map)['tiles'] as List)[level] as List) sha as String,
    ];
    expect(shas, hasLength(24));

    // Every tile request is answered from the cache, byte for byte, with the network off.
    final answers = (await tester.runAsync(() => Future.wait([for (final sha in shas) get(Uri.parse('$base/$sha.jpg'))])))!;
    for (var i = 0; i < shas.length; i++) {
      expect(answers[i].status, 200, reason: shas[i]);
      expect(answers[i].body, File('$renderDir/tiles/${shas[i]}.jpg').readAsBytesSync(), reason: shas[i]);
    }
    expect(services.tileServer.served.where((r) => r.status == 200).every((r) => r.cached), isTrue);
    expect(log.tileRequests.length, fetchedOnline, reason: 'nothing went to the network');

    // A tile this phone never saw: 504, not a hang.
    final missing = (await tester.runAsync(() => get(Uri.parse('$base/${'0' * 64}.jpg'))))!;
    expect(missing.status, 504);

    // The page reports where the person looks; nudges and presence use it.
    surface.emit('{"type":"turn","yaw":90,"pitch":-5}');
    expect(c.yawDeg, 90);
    expect(c.pitchDeg, -5);

    await tester.pumpWidget(const SizedBox());
    await tester.runAsync(() async {
      c.dispose();
      await services.tileServer.stop();
    });
  });

  testWidgets('a manifest of an unknown MAJOR asks for an update instead of showing', (tester) async {
    late Services services;
    late ProjectController c;
    await tester.runAsync(() async {
      HttpOverrides.global = null;
      final log = FakeLog(projectId: pid)..follow();
      log.manifest = {...log.manifest!, 'schema': 'truebex-tiles/2'};
      services = await testServices(log);
      await services.auth.signInWithPassword('alex@example.com', 'password123');
      await services.engine.syncProject(pid);
      log.online = false;
      c = ProjectController(services, pid, connectivity: const Stream.empty());
      await c.start();
    });
    await tester.pumpWidget(app(ProjectScreen(services: services, projectId: pid, onSignedOut: () {}, controller: c, surface: (_) => FakeSurface())));
    await tester.pump();
    expect(find.text('Update needed: this panorama needs a newer version of Truebex.'), findsOneWidget);
    expect(find.byKey(const Key('panorama')), findsNothing);
    await tester.pumpWidget(const SizedBox());
    await tester.runAsync(() async => c.dispose());
  });
}
