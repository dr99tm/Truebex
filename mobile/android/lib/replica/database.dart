// The phone's copy of what the person opened (PF10 Design: Data): SQLite through
// drift. The log is kept as the server sends it — every pulled operation with
// its delta as an opaque blob that the phone never decodes — beside the outbox
// of the phone's own `action` operations, the newest snapshot digest and the
// followed sets' manifests per project, the tile cache's index, and a few
// values (the account, prices). Signing out deletes the file.

import 'package:drift/drift.dart';
import 'package:drift_flutter/drift_flutter.dart';
import 'package:path_provider/path_provider.dart';

part 'database.g.dart';

/// Projects I own or that are shared with me (5.2), with this phone's progress.
class Projects extends Table {
  TextColumn get projectId => text()();
  TextColumn get name => text()();
  TextColumn get role => text()();
  TextColumn get ownerName => text().nullable()();

  /// The server's head as last seen (a record or a pull).
  IntColumn get headSeq => integer().withDefault(const Constant(0))();

  /// The highest server_seq stored on the phone: every operation up to it is here.
  IntColumn get pulledSeq => integer().withDefault(const Constant(0))();

  /// Starred projects stay offline: their tiles are prefetched on unmetered networks.
  BoolColumn get starred => boolean().withDefault(const Constant(false))();

  /// The 5.3 record as JSON (members with author ids, quota), when opened.
  TextColumn get record => text().nullable()();
  TextColumn get updatedAt => text().nullable()();
  DateTimeColumn get syncedAt => dateTime().nullable()();

  /// The followed set the phone shows.
  TextColumn get setId => text().nullable()();

  @override
  Set<Column> get primaryKey => {projectId};
}

/// The replica of the log (5.7): pulled pages of ≤ 1000, in server order.
class Ops extends Table {
  TextColumn get projectId => text()();
  IntColumn get serverSeq => integer()();
  TextColumn get opId => text()();
  TextColumn get replicaId => text()();
  TextColumn get author => text()();
  TextColumn get authorKind => text()();
  TextColumn get kind => text()();
  TextColumn get name => text()();
  TextColumn get at => text()();
  IntColumn get baseSeq => integer()();

  /// JSON array of 32-hex ids.
  TextColumn get touched => text()();
  TextColumn get deltaFormat => text().nullable()();

  /// The O5 delta exactly as it arrived (base64 text), never decoded on the phone.
  BlobColumn get delta => blob().nullable()();
  TextColumn get action => text().nullable()();
  TextColumn get restore => text().nullable()();

  @override
  Set<Column> get primaryKey => {projectId, serverSeq};
}

/// The phone's own operations: pending until the server answers (§6.3).
@DataClassName('OutboxEntryRow')
class OutboxEntries extends Table {
  TextColumn get opId => text()();
  TextColumn get projectId => text()();

  /// The `action` operation as sent (JSON), unchanged between tries.
  TextColumn get op => text()();

  /// pending, accepted, rejected or failed.
  TextColumn get state => text()();

  /// What the person did, as the app lists it ("Floor finish: Oak boards").
  TextColumn get label => text()();

  /// The entity the edit concerns, for its badge.
  TextColumn get subject => text().nullable()();
  IntColumn get createdAt => integer()();
  IntColumn get serverSeq => integer().nullable()();

  /// JSON `[{op_id, server_seq, author, name}]`: the operations that won.
  TextColumn get winning => text().nullable()();
  TextColumn get reason => text().nullable()();

  /// The rejection notice was shown.
  BoolColumn get notified => boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {opId};
}

/// The newest snapshot's project digest (`truebex-project-digest/1`).
class Digests extends Table {
  TextColumn get projectId => text()();
  TextColumn get snapshotId => text()();
  IntColumn get atSeq => integer()();
  TextColumn get createdAt => text()();
  TextColumn get sha256 => text()();
  TextColumn get body => text()();

  @override
  Set<Column> get primaryKey => {projectId};
}

/// The followed sets' newest state (`{rev, job_id, at_seq, manifest}`).
class Manifests extends Table {
  TextColumn get projectId => text()();
  TextColumn get setId => text()();
  IntColumn get rev => integer()();
  IntColumn get atSeq => integer()();
  TextColumn get body => text()();

  @override
  Set<Column> get primaryKey => {projectId, setId};
}

/// The tile cache's index: files `tiles/<sha256>.jpg`, least recently used out.
class Tiles extends Table {
  TextColumn get sha => text()();
  IntColumn get bytes => integer()();
  IntColumn get lastUsed => integer()();

  @override
  Set<Column> get primaryKey => {sha};
}

class KeyValues extends Table {
  TextColumn get key => text()();
  TextColumn get value => text()();

  @override
  Set<Column> get primaryKey => {key};
}

@DriftDatabase(tables: [Projects, Ops, OutboxEntries, Digests, Manifests, Tiles, KeyValues])
class ReplicaDb extends _$ReplicaDb {
  ReplicaDb(super.executor);

  /// The app's database file; shared by the app and the background sync of one process.
  factory ReplicaDb.open() => ReplicaDb(
        driftDatabase(
          name: 'truebex-replica',
          native: DriftNativeOptions(
            shareAcrossIsolates: true,
            databaseDirectory: getApplicationSupportDirectory,
          ),
        ),
      );

  @override
  int get schemaVersion => 1;

  @override
  MigrationStrategy get migration => MigrationStrategy(
        onCreate: (m) async {
          await m.createAll();
          await customStatement('CREATE INDEX ops_by_op_id ON ops (project_id, op_id)');
          await customStatement('CREATE INDEX outbox_by_project ON outbox_entries (project_id, state, created_at)');
          await customStatement('CREATE INDEX tiles_by_use ON tiles (last_used)');
        },
      );

  Future<String?> getValue(String key) async =>
      (await (select(keyValues)..where((t) => t.key.equals(key))).getSingleOrNull())?.value;

  Future<void> setValue(String key, String value) =>
      into(keyValues).insertOnConflictUpdate(KeyValuesCompanion.insert(key: key, value: value));

  Future<void> removeValue(String key) => (delete(keyValues)..where((t) => t.key.equals(key))).go();

  /// Everything, for sign-out.
  Future<void> wipe() => transaction(() async {
        for (final table in allTables) {
          await delete(table).go();
        }
      });
}
