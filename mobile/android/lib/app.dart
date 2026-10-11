import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'l10n/app_localizations.dart';
import 'screens/projects_screen.dart';
import 'screens/sign_in_screen.dart';
import 'services.dart';
import 'ui/style.dart';

class TruebexApp extends StatefulWidget {
  const TruebexApp({super.key, required this.services});

  final Services services;

  @override
  State<TruebexApp> createState() => _TruebexAppState();
}

class _TruebexAppState extends State<TruebexApp> with WidgetsBindingObserver {
  late bool _signedIn = widget.services.session.signedIn;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    if (_signedIn) unawaited(widget.services.scheduler.start());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Edits still waiting when the app goes away are sent by the one-off job when online.
    if (state == AppLifecycleState.paused && _signedIn) unawaited(_queueIfWaiting());
  }

  Future<void> _queueIfWaiting() async {
    if ((await widget.services.replica.pendingCounts()).isNotEmpty) await widget.services.scheduler.syncWhenOnline();
  }

  void _onSignedIn() {
    setState(() => _signedIn = true);
    unawaited(widget.services.notifier?.askPermission());
  }

  void _onSignedOut() => setState(() => _signedIn = false);

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Truebex',
        theme: truebexTheme(),
        localizationsDelegates: const [S.delegate, GlobalMaterialLocalizations.delegate, GlobalWidgetsLocalizations.delegate],
        supportedLocales: S.supportedLocales,
        home: _signedIn
            ? ProjectsScreen(services: widget.services, onSignedOut: _onSignedOut)
            : SignInScreen(services: widget.services, onSignedIn: _onSignedIn),
      );
}
