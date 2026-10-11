// The panorama web view's only server (PF10 Scope 3): a loopback HTTP server in
// the app that answers the viewer's requests — PF9's viewer bundle from the
// app's assets, and every tile from the tile cache first. A tile the cache does
// not hold is fetched from the manifest's `tiles_base`, checked against its
// name and kept; with the network off, cached tiles still answer and the rest
// answer 504, so the panorama shows what this phone has seen.
//
// It listens on 127.0.0.1 only (the network security config allows cleartext
// to that address and nothing else) under a random path, so another app on the
// phone cannot read through it.

import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import '../actions/actions.dart';
import 'tile_cache.dart';

typedef TileFetch = Future<Uint8List> Function(Uri url);
typedef AssetRead = Future<Uint8List?> Function(String name);

const _types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
};

class TileServer {
  TileServer({required this.cache, required this.fetch, required this.assets});

  final TileCache cache;

  /// Fetches a remote tile; throws when offline.
  final TileFetch fetch;

  /// Reads a file of the viewer bundle (`assets/viewer/<name>`).
  final AssetRead assets;

  /// The manifest's `tiles_base` the misses come from.
  String? remoteBase;

  final String token = hex32();
  HttpServer? _server;
  final Map<String, Future<Uint8List?>> _inflight = {};

  /// What the server answered, newest last (the offline test and diagnostics read it).
  final List<({String sha, int status, bool cached})> served = [];

  int get port => _server?.port ?? 0;
  Uri get origin => Uri.parse('http://127.0.0.1:$port');
  Uri get viewerUrl => origin.replace(path: '/$token/viewer/index.html');

  /// The `tiles_base` the viewer is given: this server.
  String get localTilesBase => '${origin.toString()}/$token/tiles';

  Future<void> start() async {
    if (_server != null) return;
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    _server = server;
    server.listen((req) => unawaited(_handle(req)));
  }

  Future<void> stop() async {
    await _server?.close(force: true);
    _server = null;
  }

  Future<void> _handle(HttpRequest req) async {
    final res = req.response;
    try {
      final parts = req.uri.pathSegments;
      if (req.method != 'GET' || parts.length < 3 || parts[0] != token) {
        res.statusCode = HttpStatus.notFound;
      } else if (parts[1] == 'viewer') {
        await _asset(parts.sublist(2).join('/'), res);
      } else if (parts[1] == 'tiles' && parts.length == 3 && parts[2].endsWith('.jpg')) {
        await _tile(parts[2].substring(0, parts[2].length - 4), res);
      } else {
        res.statusCode = HttpStatus.notFound;
      }
    } catch (_) {
      res.statusCode = HttpStatus.internalServerError;
    } finally {
      await res.close();
    }
  }

  Future<void> _asset(String name, HttpResponse res) async {
    if (name.contains('..')) {
      res.statusCode = HttpStatus.notFound;
      return;
    }
    final bytes = await assets(name);
    if (bytes == null) {
      res.statusCode = HttpStatus.notFound;
      return;
    }
    final dot = name.lastIndexOf('.');
    res.headers.set(HttpHeaders.contentTypeHeader, _types[dot < 0 ? '' : name.substring(dot)] ?? 'application/octet-stream');
    res.headers.set(HttpHeaders.cacheControlHeader, 'no-store');
    res.add(bytes);
  }

  Future<void> _tile(String sha, HttpResponse res) async {
    if (!isTileSha(sha)) {
      res.statusCode = HttpStatus.notFound;
      return;
    }
    final cached = await cache.get(sha);
    if (cached != null) {
      served.add((sha: sha, status: 200, cached: true));
      _jpeg(res, cached);
      return;
    }
    final fetched = await _once(sha);
    if (fetched == null) {
      served.add((sha: sha, status: 504, cached: false));
      res.statusCode = HttpStatus.gatewayTimeout;
      return;
    }
    served.add((sha: sha, status: 200, cached: false));
    _jpeg(res, fetched);
  }

  void _jpeg(HttpResponse res, Uint8List bytes) {
    res.headers.set(HttpHeaders.contentTypeHeader, 'image/jpeg');
    res.headers.set(HttpHeaders.cacheControlHeader, 'public, max-age=31536000, immutable');
    res.add(bytes);
  }

  /// One download per tile at a time, however many requests ask for it.
  Future<Uint8List?> _once(String sha) => _inflight[sha] ??= _download(sha).whenComplete(() {
        _inflight.remove(sha);
      });

  /// A tile from the network, kept when its bytes match its name; null offline.
  Future<Uint8List?> _download(String sha) async {
    final base = remoteBase;
    if (base == null) return null;
    try {
      final bytes = await fetch(Uri.parse('${base.replaceAll(RegExp(r'/$'), '')}/$sha.jpg'));
      return await cache.put(sha, bytes) ? bytes : null;
    } catch (_) {
      return null;
    }
  }

  /// Fetch the tiles of a view ahead of time (starred projects, other rooms); returns how many were added.
  Future<int> prefetch(Iterable<String> shas, {bool Function()? keepGoing}) async {
    var added = 0;
    for (final sha in shas) {
      if (keepGoing != null && !keepGoing()) break;
      if (await cache.has(sha)) continue;
      if (await _once(sha) != null) added++;
    }
    return added;
  }
}
