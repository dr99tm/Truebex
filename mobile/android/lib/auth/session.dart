// The session and the per-project replica ids, in Android's Keystore-backed
// encrypted storage (never plain preferences, never logs). The app's data is
// excluded from backups (AndroidManifest.xml), so the token never leaves the
// phone; signing out deletes it with the replica and the tiles.

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../actions/actions.dart';

/// Where secrets live: Keystore-backed on the phone, a map in tests.
abstract class SecretStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
  Future<void> deleteAll();
}

class KeystoreSecrets implements SecretStore {
  KeystoreSecrets() : _storage = const FlutterSecureStorage(aOptions: AndroidOptions(resetOnError: true));

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) => _storage.write(key: key, value: value);

  @override
  Future<void> delete(String key) => _storage.delete(key: key);

  @override
  Future<void> deleteAll() => _storage.deleteAll();
}

class MemorySecrets implements SecretStore {
  final Map<String, String> values = {};

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async => values[key] = value;

  @override
  Future<void> delete(String key) async => values.remove(key);

  @override
  Future<void> deleteAll() async => values.clear();
}

/// How the person signed in: Google sessions are renewed silently when they lapse.
enum SignInMethod { password, google }

class Session {
  Session(this._store);

  final SecretStore _store;
  String? _token;
  SignInMethod? _method;
  final Map<String, String> _replicas = {};

  static const _tokenKey = 'session.token';
  static const _methodKey = 'session.method';
  static const _emailKey = 'session.email';

  /// The token for `Authorization: Bearer` (read synchronously by the API client).
  String? get token => _token;
  SignInMethod? get method => _method;
  bool get signedIn => _token != null;

  Future<void> load() async {
    _token = await _store.read(_tokenKey);
    final m = await _store.read(_methodKey);
    _method = m == null ? null : SignInMethod.values.where((v) => v.name == m).firstOrNull;
  }

  Future<String?> email() => _store.read(_emailKey);

  Future<void> save(String token, SignInMethod method, String email) async {
    _token = token;
    _method = method;
    await _store.write(_tokenKey, token);
    await _store.write(_methodKey, method.name);
    await _store.write(_emailKey, email);
  }

  /// The session lapsed (401): forget the token, keep how the person signs in.
  Future<void> expire() async {
    _token = null;
    await _store.delete(_tokenKey);
  }

  /// One replica id per installation and project, kept for good (§6.2).
  Future<String> replicaId(String projectId) async {
    final cached = _replicas[projectId];
    if (cached != null) return cached;
    final key = 'replica.$projectId';
    var id = await _store.read(key);
    if (id == null || !isHex32(id)) {
      id = hex32();
      await _store.write(key, id);
    }
    _replicas[projectId] = id;
    return id;
  }

  Future<void> clear() async {
    _token = null;
    _method = null;
    _replicas.clear();
    await _store.deleteAll();
  }
}
