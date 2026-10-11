// The screens as a person uses them: sign in with e-mail and password, the
// project list with its sync state ("3 edits waiting", "Synced …") and the
// star, the project's sheet (Rooms from the digest, Edit, History, People),
// and Settings signing out.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:truebex/actions/actions.dart';
import 'package:truebex/app.dart';
import 'package:truebex/l10n/app_localizations.dart';
import 'package:truebex/screens/projects_screen.dart';
import 'package:truebex/screens/settings_screen.dart';
import 'package:truebex/screens/sign_in_screen.dart';
import 'package:truebex/services.dart';

import 'helpers.dart';

const pid = 'a0000000000000000000000000000001';

Widget app(Widget home) => MaterialApp(
      localizationsDelegates: const [S.delegate, GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
      supportedLocales: S.supportedLocales,
      home: home,
    );

/// Let the screen's own futures (database, stand-in server) finish.
Future<void> settle(WidgetTester tester) async {
  for (var i = 0; i < 5; i++) {
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 30)));
    await tester.pump();
  }
}

void main() {
  setUp(() => HttpOverrides.global = null);

  testWidgets('sign in with e-mail and password', (tester) async {
    final log = FakeLog(projectId: pid);
    final services = (await tester.runAsync(() => testServices(log)))!;
    var signedIn = 0;
    await tester.pumpWidget(app(SignInScreen(services: services, onSignedIn: () => signedIn++)));
    expect(find.text('Sign in to open your projects'), findsOneWidget);
    expect(find.text('Continue with Google'), findsOneWidget);

    // Offline: the message says so and nothing is saved.
    log.online = false;
    await tester.enterText(find.byKey(const Key('email')), 'alex@example.com');
    await tester.enterText(find.byKey(const Key('password')), 'password123');
    await tester.tap(find.byKey(const Key('signIn')));
    await settle(tester);
    expect(find.byKey(const Key('signInError')), findsOneWidget);
    expect(find.textContaining("Can't reach the Truebex server"), findsOneWidget);
    expect(signedIn, 0);

    log.online = true;
    await tester.tap(find.byKey(const Key('signIn')));
    await settle(tester);
    expect(signedIn, 1);
    expect(services.session.token, 'token-1');
    expect((await tester.runAsync(() => services.replica.json('me')))!['author_id'], alexAuthor);
  });

  testWidgets('the project list shows the role, the sync state and the star', (tester) async {
    final log = FakeLog(projectId: pid);
    late Services services;
    await tester.runAsync(() async {
      services = await testServices(log);
      await services.auth.signInWithPassword('alex@example.com', 'password123');
      await services.engine.syncProject(pid);
      // Two edits made offline wait in the outbox.
      for (final ref in ['c0000000000000000000000000000001', 'c0000000000000000000000000000002']) {
        final op = buildActionOp(author: alexAuthor, replicaId: await services.session.replicaId(pid), baseSeq: 0, session: hex32(),
            name: 'Move', call: moveBy([ref], [0, 50, 0]));
        await services.outbox.add(pid, op.toJson(), label: 'Move');
      }
    });
    log.online = false;
    await tester.pumpWidget(app(ProjectsScreen(services: services, onSignedOut: () {})));
    await settle(tester);
    expect(find.text('House'), findsOneWidget);
    expect(find.textContaining('Editor'), findsOneWidget);
    expect(find.textContaining('2 edits waiting'), findsOneWidget);
    expect(find.byKey(const Key('offlineBanner')), findsOneWidget);

    await tester.tap(find.byKey(const Key('star-$pid')));
    await settle(tester);
    expect((await tester.runAsync(() => services.replica.project(pid)))!.starred, isTrue);
    expect(find.byIcon(Icons.star), findsOneWidget);

    // Back online: the edits go out and the state reads "Synced just now".
    log.online = true;
    await tester.runAsync(() => services.engine.syncAll());
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(app(ProjectsScreen(services: services, onSignedOut: () {})));
    await settle(tester);
    expect(find.textContaining('Synced just now'), findsOneWidget);
    expect(log.ops, hasLength(2));
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('settings: storage, clear cache, sign out removes everything', (tester) async {
    final log = FakeLog(projectId: pid)..follow();
    late Services services;
    await tester.runAsync(() async {
      services = await testServices(log);
      await services.auth.signInWithPassword('alex@example.com', 'password123');
      await services.engine.syncProject(pid);
      await services.replica.setStarred(pid, true);
      await services.engine.syncAll(unmetered: true);
    });
    var signedOut = 0;
    await tester.pumpWidget(app(SettingsScreen(services: services, onSignedOut: () => signedOut++)));
    await settle(tester);
    expect(find.text('alex@example.com'), findsOneWidget);
    expect(find.textContaining('Panorama tiles'), findsOneWidget);
    expect((await tester.runAsync(() => services.tiles.size()))!, greaterThan(0));
    await tester.tap(find.byKey(const Key('clearCache')));
    await settle(tester);
    expect((await tester.runAsync(() => services.tiles.size()))!, 0);
    expect(find.textContaining('Panorama tiles cleared'), findsOneWidget);

    await tester.tap(find.byKey(const Key('signOut')));
    await settle(tester);
    expect(signedOut, 1);
    expect(services.session.token, isNull);
    expect(await tester.runAsync(() => services.replica.projects()), isEmpty);
  });

  testWidgets('the app opens on sign-in, then the projects', (tester) async {
    final log = FakeLog(projectId: pid);
    final services = (await tester.runAsync(() => testServices(log)))!;
    await tester.pumpWidget(TruebexApp(services: services));
    expect(find.text('Sign in to open your projects'), findsOneWidget);
    await tester.enterText(find.byKey(const Key('email')), 'alex@example.com');
    await tester.enterText(find.byKey(const Key('password')), 'password123');
    await tester.tap(find.byKey(const Key('signIn')));
    await settle(tester);
    expect(find.text('Your projects'), findsOneWidget);
    expect(find.text('House'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
