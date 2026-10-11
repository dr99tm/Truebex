// Signing in and out (PF10 Scope 6): e-mail and password (`/auth/login`) or
// Google through Android's Credential Manager with the Web client id as the
// server client id, then `/auth/google` — the same audience the website's
// Google button uses, so the server takes the token unchanged. When the 24 h
// session lapses, a Google account is signed in again silently; a password
// account signs in again by hand (the password is never stored).

import 'package:google_sign_in/google_sign_in.dart';

import '../api/api.dart';
import '../config.dart';
import '../replica/replica.dart';
import '../viewer/tile_cache.dart';
import 'session.dart';

/// Where a Google ID token comes from (Credential Manager on the phone).
abstract class GoogleTokens {
  bool get available;

  /// An ID token for the server client id; null when the person cancelled or none is at hand.
  Future<String?> idToken({required bool silent});
  Future<void> signOut();
}

class CredentialManagerGoogle implements GoogleTokens {
  bool _initialised = false;

  @override
  bool get available => Config.googleServerClientId.isNotEmpty;

  Future<void> _init() async {
    if (_initialised) return;
    await GoogleSignIn.instance.initialize(serverClientId: Config.googleServerClientId);
    _initialised = true;
  }

  @override
  Future<String?> idToken({required bool silent}) async {
    if (!available) return null;
    await _init();
    try {
      final account = silent
          ? await GoogleSignIn.instance.attemptLightweightAuthentication()
          : await GoogleSignIn.instance.authenticate();
      return account?.authentication.idToken;
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) return null;
      if (silent) return null;
      rethrow;
    }
  }

  @override
  Future<void> signOut() async {
    if (!available) return;
    await _init();
    await GoogleSignIn.instance.signOut();
  }
}

class AuthService {
  AuthService({required this.api, required this.session, required this.replica, required this.tiles, required this.google, this.onSignedIn, this.onSignedOut});

  final TruebexApi api;
  final Session session;
  final Replica replica;
  final TileCache tiles;
  final GoogleTokens google;
  final Future<void> Function()? onSignedIn;
  final Future<void> Function()? onSignedOut;

  Future<void> _start(Token token, SignInMethod method) async {
    final before = (await replica.json('me'))?['id'];
    if (before != null && before != token.user.id) {
      // Another account on this phone: its copy is not this one's.
      await replica.db.wipe();
      await tiles.clear();
    }
    await session.save(token.accessToken, method, token.user.email);
    await replica.putJson('me', {
      'id': token.user.id,
      'email': token.user.email,
      'name': token.user.name,
      'author_id': token.user.authorId,
    });
    await onSignedIn?.call();
  }

  Future<void> signInWithPassword(String email, String password) async =>
      _start(await api.login(email.trim(), password), SignInMethod.password);

  /// False when the person closed the account picker.
  Future<bool> signInWithGoogle() async {
    final idToken = await google.idToken(silent: false);
    if (idToken == null) return false;
    await _start(await api.google(idToken), SignInMethod.google);
    return true;
  }

  /// The session lapsed: a Google account signs in again without the person.
  Future<bool> renewSilently() async {
    if (session.method != SignInMethod.google || !google.available) return false;
    try {
      final idToken = await google.idToken(silent: true);
      if (idToken == null) return false;
      final token = await api.google(idToken);
      await session.save(token.accessToken, SignInMethod.google, token.user.email);
      return true;
    } catch (_) {
      return false;
    }
  }

  /// Nothing of the account stays on the phone: the replica, the tiles and the token go.
  Future<void> signOut() async {
    await onSignedOut?.call();
    await replica.db.wipe();
    await tiles.clear();
    await session.clear();
    try {
      await google.signOut();
    } catch (_) {
      // Not signed in with Google on this phone.
    }
  }
}
