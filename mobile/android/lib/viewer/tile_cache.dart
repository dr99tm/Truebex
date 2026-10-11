// The tile cache (PF10 Design: Data): files `tiles/<sha256>.jpg`, content
// addressed like the server's (a tile's name is the SHA-256 of its bytes, so a
// corrupt download never enters the cache), with an index in the replica
// database. Past the budget (500 MB) the least recently used tiles go first.

import 'dart:async';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:drift/drift.dart';
import 'package:path/path.dart' as p;

import '../replica/database.dart';

final _sha = RegExp(r'^[0-9a-f]{64}$');

bool isTileSha(String value) => _sha.hasMatch(value);

class TileCache {
  TileCache(this.directory, this.db, {this.budgetBytes = 500 * 1024 * 1024, int Function()? clock})
      : _clock = clock ?? (() => DateTime.now().millisecondsSinceEpoch);

  final Directory directory;
  final ReplicaDb db;
  final int budgetBytes;
  final int Function() _clock;
  int _lastTick = 0;

  /// Strictly increasing, so two reads in one millisecond still order.
  int _now() {
    final t = _clock();
    _lastTick = t > _lastTick ? t : _lastTick + 1;
    return _lastTick;
  }

  File _file(String sha) => File(p.join(directory.path, '$sha.jpg'));

  Future<bool> has(String sha) async =>
      await (db.select(db.tiles)..where((t) => t.sha.equals(sha))).getSingleOrNull() != null;

  /// The tile's bytes, or null; a hit counts as a use.
  Future<Uint8List?> get(String sha) async {
    if (!isTileSha(sha)) return null;
    final row = await (db.select(db.tiles)..where((t) => t.sha.equals(sha))).getSingleOrNull();
    if (row == null) return null;
    final file = _file(sha);
    if (!await file.exists()) {
      await (db.delete(db.tiles)..where((t) => t.sha.equals(sha))).go();
      return null;
    }
    await (db.update(db.tiles)..where((t) => t.sha.equals(sha))).write(TilesCompanion(lastUsed: Value(_now())));
    return file.readAsBytes();
  }

  /// Keep a tile; false when its bytes are not the tile `sha` names.
  Future<bool> put(String sha, Uint8List bytes) async {
    if (!isTileSha(sha) || sha256.convert(bytes).toString() != sha) return false;
    await directory.create(recursive: true);
    final file = _file(sha);
    final tmp = File('${file.path}.part');
    await tmp.writeAsBytes(bytes, flush: true);
    await tmp.rename(file.path);
    await db.into(db.tiles).insertOnConflictUpdate(TilesCompanion.insert(sha: sha, bytes: bytes.length, lastUsed: _now()));
    await evict();
    return true;
  }

  Future<int> size() async {
    final total = db.tiles.bytes.sum();
    final row = await (db.selectOnly(db.tiles)..addColumns([total])).getSingle();
    return row.read(total) ?? 0;
  }

  /// Least recently used out until the cache fits its budget.
  Future<int> evict() async {
    var used = await size();
    if (used <= budgetBytes) return 0;
    var removed = 0;
    final oldest = await (db.select(db.tiles)..orderBy([(t) => OrderingTerm.asc(t.lastUsed)])).get();
    for (final row in oldest) {
      if (used <= budgetBytes) break;
      final file = _file(row.sha);
      if (await file.exists()) await file.delete();
      await (db.delete(db.tiles)..where((t) => t.sha.equals(row.sha))).go();
      used -= row.bytes;
      removed++;
    }
    return removed;
  }

  Future<void> clear() async {
    await db.delete(db.tiles).go();
    if (await directory.exists()) await directory.delete(recursive: true);
  }
}
