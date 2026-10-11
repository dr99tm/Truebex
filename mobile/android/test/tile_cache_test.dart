// tile_cache_lru_budget: past the budget the least recently used tiles go first;
// a tile whose bytes are not the SHA-256 its name says never enters the cache.

import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:truebex/viewer/tile_cache.dart';

import 'helpers.dart';

Uint8List tile(int n, int size) => Uint8List.fromList(List.generate(size, (i) => (i * 31 + n) % 251));
String shaOf(Uint8List b) => sha256.convert(b).toString();

void main() {
  test('tile_cache_lru_budget', () async {
    final dir = await Directory.systemTemp.createTemp('tiles');
    var clock = 0;
    final cache = TileCache(dir, memoryDb(), budgetBytes: 3000, clock: () => clock += 10);
    final tiles = [for (var i = 0; i < 4; i++) tile(i, 1000)];
    final shas = [for (final t in tiles) shaOf(t)];
    for (var i = 0; i < 3; i++) {
      expect(await cache.put(shas[i], tiles[i]), isTrue);
    }
    expect(await cache.size(), 3000);
    // Tile 0 is read again: tile 1 is now the least recently used.
    expect(await cache.get(shas[0]), tiles[0]);
    expect(await cache.put(shas[3], tiles[3]), isTrue);
    expect(await cache.size(), 3000);
    expect(await cache.has(shas[1]), isFalse);
    expect(File('${dir.path}/${shas[1]}.jpg').existsSync(), isFalse);
    for (final i in [0, 2, 3]) {
      expect(await cache.get(shas[i]), tiles[i], reason: 'tile $i');
    }
    // Order of use now 0, 2, 3 (oldest first): a bigger tile pushes out two.
    final big = tile(9, 1900);
    expect(await cache.put(shaOf(big), big), isTrue);
    expect(await cache.has(shas[0]), isFalse);
    expect(await cache.has(shas[2]), isFalse);
    expect(await cache.has(shas[3]), isTrue);
    expect(await cache.size(), 2900);

    await cache.clear();
    expect(await cache.size(), 0);
    expect(dir.existsSync(), isFalse);
  });

  test('a tile whose bytes are not its name is refused', () async {
    final dir = await Directory.systemTemp.createTemp('tiles');
    final cache = TileCache(dir, memoryDb());
    final t = tile(1, 100);
    expect(await cache.put(shaOf(tile(2, 100)), t), isFalse);
    expect(await cache.put('not-a-sha', t), isFalse);
    expect(await cache.size(), 0);
    expect(await cache.get(shaOf(t)), isNull);
    await dir.delete(recursive: true);
  });

  test('the budget is 500 MB by default', () {
    expect(TileCache(Directory.systemTemp, memoryDb()).budgetBytes, 500 * 1024 * 1024);
  });
}
