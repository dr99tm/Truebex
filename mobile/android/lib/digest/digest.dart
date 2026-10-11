// The snapshot's project digest (`truebex-project-digest/1`, PF9's MINOR
// proposal for project-log §6.4): what a light client shows and edits without
// reading the kernel's file — storeys, rooms with their walls, saved views,
// placed products, doors and windows, themes and the market region. As PF9's
// types in src/lib/app.ts; keys this release does not know are ignored.

const digestSchema = 'truebex-project-digest/1';

List<Map<String, Object?>> _list(Object? v) => [
      if (v is List)
        for (final x in v)
          if (x is Map) x.cast<String, Object?>(),
    ];

List<num>? _nums(Object? v) => v is List && v.every((x) => x is num) ? v.cast<num>() : null;

class DigestStorey {
  DigestStorey(Map<String, Object?> j)
      : id = j['id'] as String,
        name = (j['name'] as String?) ?? '',
        elevationMm = (j['elevation_mm'] as num?)?.toDouble() ?? 0;
  final String id;
  final String name;
  final double elevationMm;
}

class DigestWall {
  DigestWall(Map<String, Object?> j)
      : id = j['id'] as String,
        name = (j['name'] as String?) ?? '',
        face = (j['face'] as String?) ?? 'left';
  final String id;
  final String name;
  final String face;
}

class DigestRoom {
  DigestRoom(Map<String, Object?> j)
      : id = j['id'] as String,
        name = (j['name'] as String?) ?? '',
        storey = j['storey'] as String?,
        areaM2 = (j['area_m2'] as num?)?.toDouble(),
        theme = j['theme'] as String?,
        walls = [for (final w in _list(j['walls'])) DigestWall(w)],
        floor = (j['finishes'] is Map) ? (j['finishes'] as Map)['floor'] : null;
  final String id;
  final String name;
  final String? storey;
  final double? areaM2;
  final String? theme;
  final List<DigestWall> walls;
  final Object? floor;
}

class DigestView {
  DigestView(Map<String, Object?> j)
      : id = j['id'] as String,
        name = (j['name'] as String?) ?? '',
        storey = j['storey'] as String?,
        room = j['room'] as String?,
        eyeMm = _nums(j['eye_mm']),
        yawDeg = (j['yaw_deg'] as num?)?.toDouble();
  final String id;
  final String name;
  final String? storey;
  final String? room;
  final List<num>? eyeMm;
  final double? yawDeg;
}

class DigestProduct {
  DigestProduct(Map<String, Object?> j)
      : id = j['id'] as String,
        name = (j['name'] as String?) ?? '',
        room = j['room'] as String?,
        category = j['category'] as String?,
        product = {
          for (final k in const ['supplier_id', 'sku', 'variant_id']) k: ((j['product'] as Map?)?[k] as String?) ?? '',
        };
  final String id;
  final String name;
  final String? room;
  final String? category;

  /// `FCadProductRef`: supplier_id, sku, variant_id.
  final Map<String, String> product;

  String get priceKey => '${product['supplier_id']}|${product['sku']}|${product['variant_id']}';
}

class DigestOpening {
  DigestOpening(Map<String, Object?> j)
      : id = j['id'] as String,
        kind = (j['kind'] as String?) ?? 'opening',
        name = (j['name'] as String?) ?? '',
        room = j['room'] as String?,
        host = j['host'] as String?;
  final String id;
  final String kind;
  final String name;
  final String? room;
  final String? host;
}

class DigestTheme {
  DigestTheme(Map<String, Object?> j)
      : id = j['id'] as String,
        name = (j['name'] as String?) ?? '';
  final String id;
  final String name;
}

class ProjectDigest {
  ProjectDigest(Map<String, Object?> j)
      : region = j['region'] as String?,
        storeys = [for (final x in _list(j['storeys'])) DigestStorey(x)],
        rooms = [for (final x in _list(j['rooms'])) DigestRoom(x)],
        views = [for (final x in _list(j['views'])) DigestView(x)],
        products = [for (final x in _list(j['products'])) DigestProduct(x)],
        openings = [for (final x in _list(j['openings'])) DigestOpening(x)],
        themes = [for (final x in _list(j['themes'])) DigestTheme(x)];

  /// Null when `json` is not a digest this release reads.
  static ProjectDigest? parse(Object? json) {
    if (json is! Map || json['schema'] != digestSchema) return null;
    return ProjectDigest(json.cast<String, Object?>());
  }

  final String? region;
  final List<DigestStorey> storeys;
  final List<DigestRoom> rooms;
  final List<DigestView> views;
  final List<DigestProduct> products;
  final List<DigestOpening> openings;
  final List<DigestTheme> themes;

  DigestRoom? room(String? id) => rooms.where((r) => r.id == id).firstOrNull;
  DigestView? view(String? id) => views.where((v) => v.id == id).firstOrNull;
  DigestProduct? product(String? id) => products.where((p) => p.id == id).firstOrNull;
  DigestOpening? opening(String? id) => openings.where((o) => o.id == id).firstOrNull;
  String? themeName(String? id) => themes.where((t) => t.id == id).firstOrNull?.name;
}

/// The digest with the snapshot it belongs to (its operation and time label a stale one).
class DigestSnapshot {
  DigestSnapshot({required this.snapshotId, required this.atSeq, required this.createdAt, required this.sha256, required this.digest});
  final String snapshotId;
  final int atSeq;
  final String createdAt;
  final String sha256;
  final ProjectDigest digest;
}
