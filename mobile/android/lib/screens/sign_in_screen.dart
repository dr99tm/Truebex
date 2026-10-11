import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/api.dart';
import '../config.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import '../ui/style.dart';

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key, required this.services, required this.onSignedIn});

  final Services services;
  final VoidCallback onSignedIn;

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    widget.services.session.email().then((e) {
      if (e != null && mounted && _email.text.isEmpty) _email.text = e;
    });
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _run(Future<bool> Function() attempt) async {
    final s = S.of(context);
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      if (await attempt()) widget.onSignedIn();
    } on ApiFailure catch (e) {
      _error = e.offline
          ? s.networkError
          : e.status == 422
              ? s.signInCheck
              : s.signInFailed(e.message);
    } catch (e) {
      _error = s.signInFailed(e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final google = widget.services.auth.google.available;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: AutofillGroup(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Center(child: Image.asset('assets/brand/lockup.png', width: 220, semanticLabel: 'Truebex')),
                    const SizedBox(height: 4),
                    Text(s.badge, textAlign: TextAlign.center, style: const TextStyle(color: Brand.accent, fontSize: 12)),
                    const SizedBox(height: 24),
                    Text(s.signInTitle, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 8),
                    Text(s.signInText, textAlign: TextAlign.center, style: const TextStyle(color: Brand.secondary)),
                    const SizedBox(height: 24),
                    TextField(
                      key: const Key('email'),
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                      autofillHints: const [AutofillHints.email],
                      decoration: InputDecoration(labelText: s.email),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      key: const Key('password'),
                      controller: _password,
                      obscureText: true,
                      textInputAction: TextInputAction.go,
                      autofillHints: const [AutofillHints.password],
                      decoration: InputDecoration(labelText: s.password),
                      onSubmitted: (_) => _busy ? null : _password.text.isEmpty ? null : _signIn(),
                    ),
                    const SizedBox(height: 16),
                    FilledButton(
                      key: const Key('signIn'),
                      onPressed: _busy ? null : _signIn,
                      child: Text(_busy ? s.signingIn : s.signIn),
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      key: const Key('google'),
                      onPressed: _busy || !google ? null : () => _run(widget.services.auth.signInWithGoogle),
                      icon: const Icon(Icons.account_circle_outlined),
                      label: Text(s.continueWithGoogle),
                    ),
                    if (!google)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(s.googleUnavailable, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, color: Brand.muted)),
                      ),
                    if (_error.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 16),
                        child: Text(_error, key: const Key('signInError'), textAlign: TextAlign.center, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                      ),
                    const SizedBox(height: 24),
                    TextButton(
                      onPressed: () => launchUrl(Uri.parse(Config.signUpUrl), mode: LaunchMode.externalApplication),
                      child: Text(s.createAccount),
                    ),
                    TextButton(
                      onPressed: () => launchUrl(Uri.parse(Config.privacyUrl), mode: LaunchMode.externalApplication),
                      child: Text(s.privacy),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _signIn() => _run(() async {
        await widget.services.auth.signInWithPassword(_email.text, _password.text);
        return true;
      });
}
