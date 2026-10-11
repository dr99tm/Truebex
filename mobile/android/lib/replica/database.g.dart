// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'database.dart';

// ignore_for_file: type=lint
class $ProjectsTable extends Projects with TableInfo<$ProjectsTable, Project> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ProjectsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _projectIdMeta = const VerificationMeta(
    'projectId',
  );
  @override
  late final GeneratedColumn<String> projectId = GeneratedColumn<String>(
    'project_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _nameMeta = const VerificationMeta('name');
  @override
  late final GeneratedColumn<String> name = GeneratedColumn<String>(
    'name',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _roleMeta = const VerificationMeta('role');
  @override
  late final GeneratedColumn<String> role = GeneratedColumn<String>(
    'role',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _ownerNameMeta = const VerificationMeta(
    'ownerName',
  );
  @override
  late final GeneratedColumn<String> ownerName = GeneratedColumn<String>(
    'owner_name',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _headSeqMeta = const VerificationMeta(
    'headSeq',
  );
  @override
  late final GeneratedColumn<int> headSeq = GeneratedColumn<int>(
    'head_seq',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  static const VerificationMeta _pulledSeqMeta = const VerificationMeta(
    'pulledSeq',
  );
  @override
  late final GeneratedColumn<int> pulledSeq = GeneratedColumn<int>(
    'pulled_seq',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
    defaultValue: const Constant(0),
  );
  static const VerificationMeta _starredMeta = const VerificationMeta(
    'starred',
  );
  @override
  late final GeneratedColumn<bool> starred = GeneratedColumn<bool>(
    'starred',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("starred" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  static const VerificationMeta _recordMeta = const VerificationMeta('record');
  @override
  late final GeneratedColumn<String> record = GeneratedColumn<String>(
    'record',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _updatedAtMeta = const VerificationMeta(
    'updatedAt',
  );
  @override
  late final GeneratedColumn<String> updatedAt = GeneratedColumn<String>(
    'updated_at',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _syncedAtMeta = const VerificationMeta(
    'syncedAt',
  );
  @override
  late final GeneratedColumn<DateTime> syncedAt = GeneratedColumn<DateTime>(
    'synced_at',
    aliasedName,
    true,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _setIdMeta = const VerificationMeta('setId');
  @override
  late final GeneratedColumn<String> setId = GeneratedColumn<String>(
    'set_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  @override
  List<GeneratedColumn> get $columns => [
    projectId,
    name,
    role,
    ownerName,
    headSeq,
    pulledSeq,
    starred,
    record,
    updatedAt,
    syncedAt,
    setId,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'projects';
  @override
  VerificationContext validateIntegrity(
    Insertable<Project> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('project_id')) {
      context.handle(
        _projectIdMeta,
        projectId.isAcceptableOrUnknown(data['project_id']!, _projectIdMeta),
      );
    } else if (isInserting) {
      context.missing(_projectIdMeta);
    }
    if (data.containsKey('name')) {
      context.handle(
        _nameMeta,
        name.isAcceptableOrUnknown(data['name']!, _nameMeta),
      );
    } else if (isInserting) {
      context.missing(_nameMeta);
    }
    if (data.containsKey('role')) {
      context.handle(
        _roleMeta,
        role.isAcceptableOrUnknown(data['role']!, _roleMeta),
      );
    } else if (isInserting) {
      context.missing(_roleMeta);
    }
    if (data.containsKey('owner_name')) {
      context.handle(
        _ownerNameMeta,
        ownerName.isAcceptableOrUnknown(data['owner_name']!, _ownerNameMeta),
      );
    }
    if (data.containsKey('head_seq')) {
      context.handle(
        _headSeqMeta,
        headSeq.isAcceptableOrUnknown(data['head_seq']!, _headSeqMeta),
      );
    }
    if (data.containsKey('pulled_seq')) {
      context.handle(
        _pulledSeqMeta,
        pulledSeq.isAcceptableOrUnknown(data['pulled_seq']!, _pulledSeqMeta),
      );
    }
    if (data.containsKey('starred')) {
      context.handle(
        _starredMeta,
        starred.isAcceptableOrUnknown(data['starred']!, _starredMeta),
      );
    }
    if (data.containsKey('record')) {
      context.handle(
        _recordMeta,
        record.isAcceptableOrUnknown(data['record']!, _recordMeta),
      );
    }
    if (data.containsKey('updated_at')) {
      context.handle(
        _updatedAtMeta,
        updatedAt.isAcceptableOrUnknown(data['updated_at']!, _updatedAtMeta),
      );
    }
    if (data.containsKey('synced_at')) {
      context.handle(
        _syncedAtMeta,
        syncedAt.isAcceptableOrUnknown(data['synced_at']!, _syncedAtMeta),
      );
    }
    if (data.containsKey('set_id')) {
      context.handle(
        _setIdMeta,
        setId.isAcceptableOrUnknown(data['set_id']!, _setIdMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {projectId};
  @override
  Project map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Project(
      projectId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}project_id'],
      )!,
      name: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}name'],
      )!,
      role: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}role'],
      )!,
      ownerName: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}owner_name'],
      ),
      headSeq: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}head_seq'],
      )!,
      pulledSeq: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}pulled_seq'],
      )!,
      starred: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}starred'],
      )!,
      record: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}record'],
      ),
      updatedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}updated_at'],
      ),
      syncedAt: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}synced_at'],
      ),
      setId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}set_id'],
      ),
    );
  }

  @override
  $ProjectsTable createAlias(String alias) {
    return $ProjectsTable(attachedDatabase, alias);
  }
}

class Project extends DataClass implements Insertable<Project> {
  final String projectId;
  final String name;
  final String role;
  final String? ownerName;

  /// The server's head as last seen (a record or a pull).
  final int headSeq;

  /// The highest server_seq stored on the phone: every operation up to it is here.
  final int pulledSeq;

  /// Starred projects stay offline: their tiles are prefetched on unmetered networks.
  final bool starred;

  /// The 5.3 record as JSON (members with author ids, quota), when opened.
  final String? record;
  final String? updatedAt;
  final DateTime? syncedAt;

  /// The followed set the phone shows.
  final String? setId;
  const Project({
    required this.projectId,
    required this.name,
    required this.role,
    this.ownerName,
    required this.headSeq,
    required this.pulledSeq,
    required this.starred,
    this.record,
    this.updatedAt,
    this.syncedAt,
    this.setId,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['project_id'] = Variable<String>(projectId);
    map['name'] = Variable<String>(name);
    map['role'] = Variable<String>(role);
    if (!nullToAbsent || ownerName != null) {
      map['owner_name'] = Variable<String>(ownerName);
    }
    map['head_seq'] = Variable<int>(headSeq);
    map['pulled_seq'] = Variable<int>(pulledSeq);
    map['starred'] = Variable<bool>(starred);
    if (!nullToAbsent || record != null) {
      map['record'] = Variable<String>(record);
    }
    if (!nullToAbsent || updatedAt != null) {
      map['updated_at'] = Variable<String>(updatedAt);
    }
    if (!nullToAbsent || syncedAt != null) {
      map['synced_at'] = Variable<DateTime>(syncedAt);
    }
    if (!nullToAbsent || setId != null) {
      map['set_id'] = Variable<String>(setId);
    }
    return map;
  }

  ProjectsCompanion toCompanion(bool nullToAbsent) {
    return ProjectsCompanion(
      projectId: Value(projectId),
      name: Value(name),
      role: Value(role),
      ownerName: ownerName == null && nullToAbsent
          ? const Value.absent()
          : Value(ownerName),
      headSeq: Value(headSeq),
      pulledSeq: Value(pulledSeq),
      starred: Value(starred),
      record: record == null && nullToAbsent
          ? const Value.absent()
          : Value(record),
      updatedAt: updatedAt == null && nullToAbsent
          ? const Value.absent()
          : Value(updatedAt),
      syncedAt: syncedAt == null && nullToAbsent
          ? const Value.absent()
          : Value(syncedAt),
      setId: setId == null && nullToAbsent
          ? const Value.absent()
          : Value(setId),
    );
  }

  factory Project.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Project(
      projectId: serializer.fromJson<String>(json['projectId']),
      name: serializer.fromJson<String>(json['name']),
      role: serializer.fromJson<String>(json['role']),
      ownerName: serializer.fromJson<String?>(json['ownerName']),
      headSeq: serializer.fromJson<int>(json['headSeq']),
      pulledSeq: serializer.fromJson<int>(json['pulledSeq']),
      starred: serializer.fromJson<bool>(json['starred']),
      record: serializer.fromJson<String?>(json['record']),
      updatedAt: serializer.fromJson<String?>(json['updatedAt']),
      syncedAt: serializer.fromJson<DateTime?>(json['syncedAt']),
      setId: serializer.fromJson<String?>(json['setId']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'projectId': serializer.toJson<String>(projectId),
      'name': serializer.toJson<String>(name),
      'role': serializer.toJson<String>(role),
      'ownerName': serializer.toJson<String?>(ownerName),
      'headSeq': serializer.toJson<int>(headSeq),
      'pulledSeq': serializer.toJson<int>(pulledSeq),
      'starred': serializer.toJson<bool>(starred),
      'record': serializer.toJson<String?>(record),
      'updatedAt': serializer.toJson<String?>(updatedAt),
      'syncedAt': serializer.toJson<DateTime?>(syncedAt),
      'setId': serializer.toJson<String?>(setId),
    };
  }

  Project copyWith({
    String? projectId,
    String? name,
    String? role,
    Value<String?> ownerName = const Value.absent(),
    int? headSeq,
    int? pulledSeq,
    bool? starred,
    Value<String?> record = const Value.absent(),
    Value<String?> updatedAt = const Value.absent(),
    Value<DateTime?> syncedAt = const Value.absent(),
    Value<String?> setId = const Value.absent(),
  }) => Project(
    projectId: projectId ?? this.projectId,
    name: name ?? this.name,
    role: role ?? this.role,
    ownerName: ownerName.present ? ownerName.value : this.ownerName,
    headSeq: headSeq ?? this.headSeq,
    pulledSeq: pulledSeq ?? this.pulledSeq,
    starred: starred ?? this.starred,
    record: record.present ? record.value : this.record,
    updatedAt: updatedAt.present ? updatedAt.value : this.updatedAt,
    syncedAt: syncedAt.present ? syncedAt.value : this.syncedAt,
    setId: setId.present ? setId.value : this.setId,
  );
  Project copyWithCompanion(ProjectsCompanion data) {
    return Project(
      projectId: data.projectId.present ? data.projectId.value : this.projectId,
      name: data.name.present ? data.name.value : this.name,
      role: data.role.present ? data.role.value : this.role,
      ownerName: data.ownerName.present ? data.ownerName.value : this.ownerName,
      headSeq: data.headSeq.present ? data.headSeq.value : this.headSeq,
      pulledSeq: data.pulledSeq.present ? data.pulledSeq.value : this.pulledSeq,
      starred: data.starred.present ? data.starred.value : this.starred,
      record: data.record.present ? data.record.value : this.record,
      updatedAt: data.updatedAt.present ? data.updatedAt.value : this.updatedAt,
      syncedAt: data.syncedAt.present ? data.syncedAt.value : this.syncedAt,
      setId: data.setId.present ? data.setId.value : this.setId,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Project(')
          ..write('projectId: $projectId, ')
          ..write('name: $name, ')
          ..write('role: $role, ')
          ..write('ownerName: $ownerName, ')
          ..write('headSeq: $headSeq, ')
          ..write('pulledSeq: $pulledSeq, ')
          ..write('starred: $starred, ')
          ..write('record: $record, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('syncedAt: $syncedAt, ')
          ..write('setId: $setId')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    projectId,
    name,
    role,
    ownerName,
    headSeq,
    pulledSeq,
    starred,
    record,
    updatedAt,
    syncedAt,
    setId,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Project &&
          other.projectId == this.projectId &&
          other.name == this.name &&
          other.role == this.role &&
          other.ownerName == this.ownerName &&
          other.headSeq == this.headSeq &&
          other.pulledSeq == this.pulledSeq &&
          other.starred == this.starred &&
          other.record == this.record &&
          other.updatedAt == this.updatedAt &&
          other.syncedAt == this.syncedAt &&
          other.setId == this.setId);
}

class ProjectsCompanion extends UpdateCompanion<Project> {
  final Value<String> projectId;
  final Value<String> name;
  final Value<String> role;
  final Value<String?> ownerName;
  final Value<int> headSeq;
  final Value<int> pulledSeq;
  final Value<bool> starred;
  final Value<String?> record;
  final Value<String?> updatedAt;
  final Value<DateTime?> syncedAt;
  final Value<String?> setId;
  final Value<int> rowid;
  const ProjectsCompanion({
    this.projectId = const Value.absent(),
    this.name = const Value.absent(),
    this.role = const Value.absent(),
    this.ownerName = const Value.absent(),
    this.headSeq = const Value.absent(),
    this.pulledSeq = const Value.absent(),
    this.starred = const Value.absent(),
    this.record = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.syncedAt = const Value.absent(),
    this.setId = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  ProjectsCompanion.insert({
    required String projectId,
    required String name,
    required String role,
    this.ownerName = const Value.absent(),
    this.headSeq = const Value.absent(),
    this.pulledSeq = const Value.absent(),
    this.starred = const Value.absent(),
    this.record = const Value.absent(),
    this.updatedAt = const Value.absent(),
    this.syncedAt = const Value.absent(),
    this.setId = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : projectId = Value(projectId),
       name = Value(name),
       role = Value(role);
  static Insertable<Project> custom({
    Expression<String>? projectId,
    Expression<String>? name,
    Expression<String>? role,
    Expression<String>? ownerName,
    Expression<int>? headSeq,
    Expression<int>? pulledSeq,
    Expression<bool>? starred,
    Expression<String>? record,
    Expression<String>? updatedAt,
    Expression<DateTime>? syncedAt,
    Expression<String>? setId,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (projectId != null) 'project_id': projectId,
      if (name != null) 'name': name,
      if (role != null) 'role': role,
      if (ownerName != null) 'owner_name': ownerName,
      if (headSeq != null) 'head_seq': headSeq,
      if (pulledSeq != null) 'pulled_seq': pulledSeq,
      if (starred != null) 'starred': starred,
      if (record != null) 'record': record,
      if (updatedAt != null) 'updated_at': updatedAt,
      if (syncedAt != null) 'synced_at': syncedAt,
      if (setId != null) 'set_id': setId,
      if (rowid != null) 'rowid': rowid,
    });
  }

  ProjectsCompanion copyWith({
    Value<String>? projectId,
    Value<String>? name,
    Value<String>? role,
    Value<String?>? ownerName,
    Value<int>? headSeq,
    Value<int>? pulledSeq,
    Value<bool>? starred,
    Value<String?>? record,
    Value<String?>? updatedAt,
    Value<DateTime?>? syncedAt,
    Value<String?>? setId,
    Value<int>? rowid,
  }) {
    return ProjectsCompanion(
      projectId: projectId ?? this.projectId,
      name: name ?? this.name,
      role: role ?? this.role,
      ownerName: ownerName ?? this.ownerName,
      headSeq: headSeq ?? this.headSeq,
      pulledSeq: pulledSeq ?? this.pulledSeq,
      starred: starred ?? this.starred,
      record: record ?? this.record,
      updatedAt: updatedAt ?? this.updatedAt,
      syncedAt: syncedAt ?? this.syncedAt,
      setId: setId ?? this.setId,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (projectId.present) {
      map['project_id'] = Variable<String>(projectId.value);
    }
    if (name.present) {
      map['name'] = Variable<String>(name.value);
    }
    if (role.present) {
      map['role'] = Variable<String>(role.value);
    }
    if (ownerName.present) {
      map['owner_name'] = Variable<String>(ownerName.value);
    }
    if (headSeq.present) {
      map['head_seq'] = Variable<int>(headSeq.value);
    }
    if (pulledSeq.present) {
      map['pulled_seq'] = Variable<int>(pulledSeq.value);
    }
    if (starred.present) {
      map['starred'] = Variable<bool>(starred.value);
    }
    if (record.present) {
      map['record'] = Variable<String>(record.value);
    }
    if (updatedAt.present) {
      map['updated_at'] = Variable<String>(updatedAt.value);
    }
    if (syncedAt.present) {
      map['synced_at'] = Variable<DateTime>(syncedAt.value);
    }
    if (setId.present) {
      map['set_id'] = Variable<String>(setId.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ProjectsCompanion(')
          ..write('projectId: $projectId, ')
          ..write('name: $name, ')
          ..write('role: $role, ')
          ..write('ownerName: $ownerName, ')
          ..write('headSeq: $headSeq, ')
          ..write('pulledSeq: $pulledSeq, ')
          ..write('starred: $starred, ')
          ..write('record: $record, ')
          ..write('updatedAt: $updatedAt, ')
          ..write('syncedAt: $syncedAt, ')
          ..write('setId: $setId, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $OpsTable extends Ops with TableInfo<$OpsTable, Op> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $OpsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _projectIdMeta = const VerificationMeta(
    'projectId',
  );
  @override
  late final GeneratedColumn<String> projectId = GeneratedColumn<String>(
    'project_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _serverSeqMeta = const VerificationMeta(
    'serverSeq',
  );
  @override
  late final GeneratedColumn<int> serverSeq = GeneratedColumn<int>(
    'server_seq',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _opIdMeta = const VerificationMeta('opId');
  @override
  late final GeneratedColumn<String> opId = GeneratedColumn<String>(
    'op_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _replicaIdMeta = const VerificationMeta(
    'replicaId',
  );
  @override
  late final GeneratedColumn<String> replicaId = GeneratedColumn<String>(
    'replica_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _authorMeta = const VerificationMeta('author');
  @override
  late final GeneratedColumn<String> author = GeneratedColumn<String>(
    'author',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _authorKindMeta = const VerificationMeta(
    'authorKind',
  );
  @override
  late final GeneratedColumn<String> authorKind = GeneratedColumn<String>(
    'author_kind',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _kindMeta = const VerificationMeta('kind');
  @override
  late final GeneratedColumn<String> kind = GeneratedColumn<String>(
    'kind',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _nameMeta = const VerificationMeta('name');
  @override
  late final GeneratedColumn<String> name = GeneratedColumn<String>(
    'name',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _atMeta = const VerificationMeta('at');
  @override
  late final GeneratedColumn<String> at = GeneratedColumn<String>(
    'at',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _baseSeqMeta = const VerificationMeta(
    'baseSeq',
  );
  @override
  late final GeneratedColumn<int> baseSeq = GeneratedColumn<int>(
    'base_seq',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _touchedMeta = const VerificationMeta(
    'touched',
  );
  @override
  late final GeneratedColumn<String> touched = GeneratedColumn<String>(
    'touched',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _deltaFormatMeta = const VerificationMeta(
    'deltaFormat',
  );
  @override
  late final GeneratedColumn<String> deltaFormat = GeneratedColumn<String>(
    'delta_format',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _deltaMeta = const VerificationMeta('delta');
  @override
  late final GeneratedColumn<Uint8List> delta = GeneratedColumn<Uint8List>(
    'delta',
    aliasedName,
    true,
    type: DriftSqlType.blob,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _actionMeta = const VerificationMeta('action');
  @override
  late final GeneratedColumn<String> action = GeneratedColumn<String>(
    'action',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _restoreMeta = const VerificationMeta(
    'restore',
  );
  @override
  late final GeneratedColumn<String> restore = GeneratedColumn<String>(
    'restore',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  @override
  List<GeneratedColumn> get $columns => [
    projectId,
    serverSeq,
    opId,
    replicaId,
    author,
    authorKind,
    kind,
    name,
    at,
    baseSeq,
    touched,
    deltaFormat,
    delta,
    action,
    restore,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'ops';
  @override
  VerificationContext validateIntegrity(
    Insertable<Op> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('project_id')) {
      context.handle(
        _projectIdMeta,
        projectId.isAcceptableOrUnknown(data['project_id']!, _projectIdMeta),
      );
    } else if (isInserting) {
      context.missing(_projectIdMeta);
    }
    if (data.containsKey('server_seq')) {
      context.handle(
        _serverSeqMeta,
        serverSeq.isAcceptableOrUnknown(data['server_seq']!, _serverSeqMeta),
      );
    } else if (isInserting) {
      context.missing(_serverSeqMeta);
    }
    if (data.containsKey('op_id')) {
      context.handle(
        _opIdMeta,
        opId.isAcceptableOrUnknown(data['op_id']!, _opIdMeta),
      );
    } else if (isInserting) {
      context.missing(_opIdMeta);
    }
    if (data.containsKey('replica_id')) {
      context.handle(
        _replicaIdMeta,
        replicaId.isAcceptableOrUnknown(data['replica_id']!, _replicaIdMeta),
      );
    } else if (isInserting) {
      context.missing(_replicaIdMeta);
    }
    if (data.containsKey('author')) {
      context.handle(
        _authorMeta,
        author.isAcceptableOrUnknown(data['author']!, _authorMeta),
      );
    } else if (isInserting) {
      context.missing(_authorMeta);
    }
    if (data.containsKey('author_kind')) {
      context.handle(
        _authorKindMeta,
        authorKind.isAcceptableOrUnknown(data['author_kind']!, _authorKindMeta),
      );
    } else if (isInserting) {
      context.missing(_authorKindMeta);
    }
    if (data.containsKey('kind')) {
      context.handle(
        _kindMeta,
        kind.isAcceptableOrUnknown(data['kind']!, _kindMeta),
      );
    } else if (isInserting) {
      context.missing(_kindMeta);
    }
    if (data.containsKey('name')) {
      context.handle(
        _nameMeta,
        name.isAcceptableOrUnknown(data['name']!, _nameMeta),
      );
    } else if (isInserting) {
      context.missing(_nameMeta);
    }
    if (data.containsKey('at')) {
      context.handle(_atMeta, at.isAcceptableOrUnknown(data['at']!, _atMeta));
    } else if (isInserting) {
      context.missing(_atMeta);
    }
    if (data.containsKey('base_seq')) {
      context.handle(
        _baseSeqMeta,
        baseSeq.isAcceptableOrUnknown(data['base_seq']!, _baseSeqMeta),
      );
    } else if (isInserting) {
      context.missing(_baseSeqMeta);
    }
    if (data.containsKey('touched')) {
      context.handle(
        _touchedMeta,
        touched.isAcceptableOrUnknown(data['touched']!, _touchedMeta),
      );
    } else if (isInserting) {
      context.missing(_touchedMeta);
    }
    if (data.containsKey('delta_format')) {
      context.handle(
        _deltaFormatMeta,
        deltaFormat.isAcceptableOrUnknown(
          data['delta_format']!,
          _deltaFormatMeta,
        ),
      );
    }
    if (data.containsKey('delta')) {
      context.handle(
        _deltaMeta,
        delta.isAcceptableOrUnknown(data['delta']!, _deltaMeta),
      );
    }
    if (data.containsKey('action')) {
      context.handle(
        _actionMeta,
        action.isAcceptableOrUnknown(data['action']!, _actionMeta),
      );
    }
    if (data.containsKey('restore')) {
      context.handle(
        _restoreMeta,
        restore.isAcceptableOrUnknown(data['restore']!, _restoreMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {projectId, serverSeq};
  @override
  Op map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Op(
      projectId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}project_id'],
      )!,
      serverSeq: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}server_seq'],
      )!,
      opId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}op_id'],
      )!,
      replicaId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}replica_id'],
      )!,
      author: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}author'],
      )!,
      authorKind: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}author_kind'],
      )!,
      kind: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}kind'],
      )!,
      name: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}name'],
      )!,
      at: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}at'],
      )!,
      baseSeq: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}base_seq'],
      )!,
      touched: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}touched'],
      )!,
      deltaFormat: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}delta_format'],
      ),
      delta: attachedDatabase.typeMapping.read(
        DriftSqlType.blob,
        data['${effectivePrefix}delta'],
      ),
      action: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}action'],
      ),
      restore: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}restore'],
      ),
    );
  }

  @override
  $OpsTable createAlias(String alias) {
    return $OpsTable(attachedDatabase, alias);
  }
}

class Op extends DataClass implements Insertable<Op> {
  final String projectId;
  final int serverSeq;
  final String opId;
  final String replicaId;
  final String author;
  final String authorKind;
  final String kind;
  final String name;
  final String at;
  final int baseSeq;

  /// JSON array of 32-hex ids.
  final String touched;
  final String? deltaFormat;

  /// The O5 delta exactly as it arrived (base64 text), never decoded on the phone.
  final Uint8List? delta;
  final String? action;
  final String? restore;
  const Op({
    required this.projectId,
    required this.serverSeq,
    required this.opId,
    required this.replicaId,
    required this.author,
    required this.authorKind,
    required this.kind,
    required this.name,
    required this.at,
    required this.baseSeq,
    required this.touched,
    this.deltaFormat,
    this.delta,
    this.action,
    this.restore,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['project_id'] = Variable<String>(projectId);
    map['server_seq'] = Variable<int>(serverSeq);
    map['op_id'] = Variable<String>(opId);
    map['replica_id'] = Variable<String>(replicaId);
    map['author'] = Variable<String>(author);
    map['author_kind'] = Variable<String>(authorKind);
    map['kind'] = Variable<String>(kind);
    map['name'] = Variable<String>(name);
    map['at'] = Variable<String>(at);
    map['base_seq'] = Variable<int>(baseSeq);
    map['touched'] = Variable<String>(touched);
    if (!nullToAbsent || deltaFormat != null) {
      map['delta_format'] = Variable<String>(deltaFormat);
    }
    if (!nullToAbsent || delta != null) {
      map['delta'] = Variable<Uint8List>(delta);
    }
    if (!nullToAbsent || action != null) {
      map['action'] = Variable<String>(action);
    }
    if (!nullToAbsent || restore != null) {
      map['restore'] = Variable<String>(restore);
    }
    return map;
  }

  OpsCompanion toCompanion(bool nullToAbsent) {
    return OpsCompanion(
      projectId: Value(projectId),
      serverSeq: Value(serverSeq),
      opId: Value(opId),
      replicaId: Value(replicaId),
      author: Value(author),
      authorKind: Value(authorKind),
      kind: Value(kind),
      name: Value(name),
      at: Value(at),
      baseSeq: Value(baseSeq),
      touched: Value(touched),
      deltaFormat: deltaFormat == null && nullToAbsent
          ? const Value.absent()
          : Value(deltaFormat),
      delta: delta == null && nullToAbsent
          ? const Value.absent()
          : Value(delta),
      action: action == null && nullToAbsent
          ? const Value.absent()
          : Value(action),
      restore: restore == null && nullToAbsent
          ? const Value.absent()
          : Value(restore),
    );
  }

  factory Op.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Op(
      projectId: serializer.fromJson<String>(json['projectId']),
      serverSeq: serializer.fromJson<int>(json['serverSeq']),
      opId: serializer.fromJson<String>(json['opId']),
      replicaId: serializer.fromJson<String>(json['replicaId']),
      author: serializer.fromJson<String>(json['author']),
      authorKind: serializer.fromJson<String>(json['authorKind']),
      kind: serializer.fromJson<String>(json['kind']),
      name: serializer.fromJson<String>(json['name']),
      at: serializer.fromJson<String>(json['at']),
      baseSeq: serializer.fromJson<int>(json['baseSeq']),
      touched: serializer.fromJson<String>(json['touched']),
      deltaFormat: serializer.fromJson<String?>(json['deltaFormat']),
      delta: serializer.fromJson<Uint8List?>(json['delta']),
      action: serializer.fromJson<String?>(json['action']),
      restore: serializer.fromJson<String?>(json['restore']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'projectId': serializer.toJson<String>(projectId),
      'serverSeq': serializer.toJson<int>(serverSeq),
      'opId': serializer.toJson<String>(opId),
      'replicaId': serializer.toJson<String>(replicaId),
      'author': serializer.toJson<String>(author),
      'authorKind': serializer.toJson<String>(authorKind),
      'kind': serializer.toJson<String>(kind),
      'name': serializer.toJson<String>(name),
      'at': serializer.toJson<String>(at),
      'baseSeq': serializer.toJson<int>(baseSeq),
      'touched': serializer.toJson<String>(touched),
      'deltaFormat': serializer.toJson<String?>(deltaFormat),
      'delta': serializer.toJson<Uint8List?>(delta),
      'action': serializer.toJson<String?>(action),
      'restore': serializer.toJson<String?>(restore),
    };
  }

  Op copyWith({
    String? projectId,
    int? serverSeq,
    String? opId,
    String? replicaId,
    String? author,
    String? authorKind,
    String? kind,
    String? name,
    String? at,
    int? baseSeq,
    String? touched,
    Value<String?> deltaFormat = const Value.absent(),
    Value<Uint8List?> delta = const Value.absent(),
    Value<String?> action = const Value.absent(),
    Value<String?> restore = const Value.absent(),
  }) => Op(
    projectId: projectId ?? this.projectId,
    serverSeq: serverSeq ?? this.serverSeq,
    opId: opId ?? this.opId,
    replicaId: replicaId ?? this.replicaId,
    author: author ?? this.author,
    authorKind: authorKind ?? this.authorKind,
    kind: kind ?? this.kind,
    name: name ?? this.name,
    at: at ?? this.at,
    baseSeq: baseSeq ?? this.baseSeq,
    touched: touched ?? this.touched,
    deltaFormat: deltaFormat.present ? deltaFormat.value : this.deltaFormat,
    delta: delta.present ? delta.value : this.delta,
    action: action.present ? action.value : this.action,
    restore: restore.present ? restore.value : this.restore,
  );
  Op copyWithCompanion(OpsCompanion data) {
    return Op(
      projectId: data.projectId.present ? data.projectId.value : this.projectId,
      serverSeq: data.serverSeq.present ? data.serverSeq.value : this.serverSeq,
      opId: data.opId.present ? data.opId.value : this.opId,
      replicaId: data.replicaId.present ? data.replicaId.value : this.replicaId,
      author: data.author.present ? data.author.value : this.author,
      authorKind: data.authorKind.present
          ? data.authorKind.value
          : this.authorKind,
      kind: data.kind.present ? data.kind.value : this.kind,
      name: data.name.present ? data.name.value : this.name,
      at: data.at.present ? data.at.value : this.at,
      baseSeq: data.baseSeq.present ? data.baseSeq.value : this.baseSeq,
      touched: data.touched.present ? data.touched.value : this.touched,
      deltaFormat: data.deltaFormat.present
          ? data.deltaFormat.value
          : this.deltaFormat,
      delta: data.delta.present ? data.delta.value : this.delta,
      action: data.action.present ? data.action.value : this.action,
      restore: data.restore.present ? data.restore.value : this.restore,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Op(')
          ..write('projectId: $projectId, ')
          ..write('serverSeq: $serverSeq, ')
          ..write('opId: $opId, ')
          ..write('replicaId: $replicaId, ')
          ..write('author: $author, ')
          ..write('authorKind: $authorKind, ')
          ..write('kind: $kind, ')
          ..write('name: $name, ')
          ..write('at: $at, ')
          ..write('baseSeq: $baseSeq, ')
          ..write('touched: $touched, ')
          ..write('deltaFormat: $deltaFormat, ')
          ..write('delta: $delta, ')
          ..write('action: $action, ')
          ..write('restore: $restore')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    projectId,
    serverSeq,
    opId,
    replicaId,
    author,
    authorKind,
    kind,
    name,
    at,
    baseSeq,
    touched,
    deltaFormat,
    $driftBlobEquality.hash(delta),
    action,
    restore,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Op &&
          other.projectId == this.projectId &&
          other.serverSeq == this.serverSeq &&
          other.opId == this.opId &&
          other.replicaId == this.replicaId &&
          other.author == this.author &&
          other.authorKind == this.authorKind &&
          other.kind == this.kind &&
          other.name == this.name &&
          other.at == this.at &&
          other.baseSeq == this.baseSeq &&
          other.touched == this.touched &&
          other.deltaFormat == this.deltaFormat &&
          $driftBlobEquality.equals(other.delta, this.delta) &&
          other.action == this.action &&
          other.restore == this.restore);
}

class OpsCompanion extends UpdateCompanion<Op> {
  final Value<String> projectId;
  final Value<int> serverSeq;
  final Value<String> opId;
  final Value<String> replicaId;
  final Value<String> author;
  final Value<String> authorKind;
  final Value<String> kind;
  final Value<String> name;
  final Value<String> at;
  final Value<int> baseSeq;
  final Value<String> touched;
  final Value<String?> deltaFormat;
  final Value<Uint8List?> delta;
  final Value<String?> action;
  final Value<String?> restore;
  final Value<int> rowid;
  const OpsCompanion({
    this.projectId = const Value.absent(),
    this.serverSeq = const Value.absent(),
    this.opId = const Value.absent(),
    this.replicaId = const Value.absent(),
    this.author = const Value.absent(),
    this.authorKind = const Value.absent(),
    this.kind = const Value.absent(),
    this.name = const Value.absent(),
    this.at = const Value.absent(),
    this.baseSeq = const Value.absent(),
    this.touched = const Value.absent(),
    this.deltaFormat = const Value.absent(),
    this.delta = const Value.absent(),
    this.action = const Value.absent(),
    this.restore = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  OpsCompanion.insert({
    required String projectId,
    required int serverSeq,
    required String opId,
    required String replicaId,
    required String author,
    required String authorKind,
    required String kind,
    required String name,
    required String at,
    required int baseSeq,
    required String touched,
    this.deltaFormat = const Value.absent(),
    this.delta = const Value.absent(),
    this.action = const Value.absent(),
    this.restore = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : projectId = Value(projectId),
       serverSeq = Value(serverSeq),
       opId = Value(opId),
       replicaId = Value(replicaId),
       author = Value(author),
       authorKind = Value(authorKind),
       kind = Value(kind),
       name = Value(name),
       at = Value(at),
       baseSeq = Value(baseSeq),
       touched = Value(touched);
  static Insertable<Op> custom({
    Expression<String>? projectId,
    Expression<int>? serverSeq,
    Expression<String>? opId,
    Expression<String>? replicaId,
    Expression<String>? author,
    Expression<String>? authorKind,
    Expression<String>? kind,
    Expression<String>? name,
    Expression<String>? at,
    Expression<int>? baseSeq,
    Expression<String>? touched,
    Expression<String>? deltaFormat,
    Expression<Uint8List>? delta,
    Expression<String>? action,
    Expression<String>? restore,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (projectId != null) 'project_id': projectId,
      if (serverSeq != null) 'server_seq': serverSeq,
      if (opId != null) 'op_id': opId,
      if (replicaId != null) 'replica_id': replicaId,
      if (author != null) 'author': author,
      if (authorKind != null) 'author_kind': authorKind,
      if (kind != null) 'kind': kind,
      if (name != null) 'name': name,
      if (at != null) 'at': at,
      if (baseSeq != null) 'base_seq': baseSeq,
      if (touched != null) 'touched': touched,
      if (deltaFormat != null) 'delta_format': deltaFormat,
      if (delta != null) 'delta': delta,
      if (action != null) 'action': action,
      if (restore != null) 'restore': restore,
      if (rowid != null) 'rowid': rowid,
    });
  }

  OpsCompanion copyWith({
    Value<String>? projectId,
    Value<int>? serverSeq,
    Value<String>? opId,
    Value<String>? replicaId,
    Value<String>? author,
    Value<String>? authorKind,
    Value<String>? kind,
    Value<String>? name,
    Value<String>? at,
    Value<int>? baseSeq,
    Value<String>? touched,
    Value<String?>? deltaFormat,
    Value<Uint8List?>? delta,
    Value<String?>? action,
    Value<String?>? restore,
    Value<int>? rowid,
  }) {
    return OpsCompanion(
      projectId: projectId ?? this.projectId,
      serverSeq: serverSeq ?? this.serverSeq,
      opId: opId ?? this.opId,
      replicaId: replicaId ?? this.replicaId,
      author: author ?? this.author,
      authorKind: authorKind ?? this.authorKind,
      kind: kind ?? this.kind,
      name: name ?? this.name,
      at: at ?? this.at,
      baseSeq: baseSeq ?? this.baseSeq,
      touched: touched ?? this.touched,
      deltaFormat: deltaFormat ?? this.deltaFormat,
      delta: delta ?? this.delta,
      action: action ?? this.action,
      restore: restore ?? this.restore,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (projectId.present) {
      map['project_id'] = Variable<String>(projectId.value);
    }
    if (serverSeq.present) {
      map['server_seq'] = Variable<int>(serverSeq.value);
    }
    if (opId.present) {
      map['op_id'] = Variable<String>(opId.value);
    }
    if (replicaId.present) {
      map['replica_id'] = Variable<String>(replicaId.value);
    }
    if (author.present) {
      map['author'] = Variable<String>(author.value);
    }
    if (authorKind.present) {
      map['author_kind'] = Variable<String>(authorKind.value);
    }
    if (kind.present) {
      map['kind'] = Variable<String>(kind.value);
    }
    if (name.present) {
      map['name'] = Variable<String>(name.value);
    }
    if (at.present) {
      map['at'] = Variable<String>(at.value);
    }
    if (baseSeq.present) {
      map['base_seq'] = Variable<int>(baseSeq.value);
    }
    if (touched.present) {
      map['touched'] = Variable<String>(touched.value);
    }
    if (deltaFormat.present) {
      map['delta_format'] = Variable<String>(deltaFormat.value);
    }
    if (delta.present) {
      map['delta'] = Variable<Uint8List>(delta.value);
    }
    if (action.present) {
      map['action'] = Variable<String>(action.value);
    }
    if (restore.present) {
      map['restore'] = Variable<String>(restore.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('OpsCompanion(')
          ..write('projectId: $projectId, ')
          ..write('serverSeq: $serverSeq, ')
          ..write('opId: $opId, ')
          ..write('replicaId: $replicaId, ')
          ..write('author: $author, ')
          ..write('authorKind: $authorKind, ')
          ..write('kind: $kind, ')
          ..write('name: $name, ')
          ..write('at: $at, ')
          ..write('baseSeq: $baseSeq, ')
          ..write('touched: $touched, ')
          ..write('deltaFormat: $deltaFormat, ')
          ..write('delta: $delta, ')
          ..write('action: $action, ')
          ..write('restore: $restore, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $OutboxEntriesTable extends OutboxEntries
    with TableInfo<$OutboxEntriesTable, OutboxEntryRow> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $OutboxEntriesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _opIdMeta = const VerificationMeta('opId');
  @override
  late final GeneratedColumn<String> opId = GeneratedColumn<String>(
    'op_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _projectIdMeta = const VerificationMeta(
    'projectId',
  );
  @override
  late final GeneratedColumn<String> projectId = GeneratedColumn<String>(
    'project_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _opMeta = const VerificationMeta('op');
  @override
  late final GeneratedColumn<String> op = GeneratedColumn<String>(
    'op',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _stateMeta = const VerificationMeta('state');
  @override
  late final GeneratedColumn<String> state = GeneratedColumn<String>(
    'state',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _labelMeta = const VerificationMeta('label');
  @override
  late final GeneratedColumn<String> label = GeneratedColumn<String>(
    'label',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _subjectMeta = const VerificationMeta(
    'subject',
  );
  @override
  late final GeneratedColumn<String> subject = GeneratedColumn<String>(
    'subject',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _createdAtMeta = const VerificationMeta(
    'createdAt',
  );
  @override
  late final GeneratedColumn<int> createdAt = GeneratedColumn<int>(
    'created_at',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _serverSeqMeta = const VerificationMeta(
    'serverSeq',
  );
  @override
  late final GeneratedColumn<int> serverSeq = GeneratedColumn<int>(
    'server_seq',
    aliasedName,
    true,
    type: DriftSqlType.int,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _winningMeta = const VerificationMeta(
    'winning',
  );
  @override
  late final GeneratedColumn<String> winning = GeneratedColumn<String>(
    'winning',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _reasonMeta = const VerificationMeta('reason');
  @override
  late final GeneratedColumn<String> reason = GeneratedColumn<String>(
    'reason',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _notifiedMeta = const VerificationMeta(
    'notified',
  );
  @override
  late final GeneratedColumn<bool> notified = GeneratedColumn<bool>(
    'notified',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("notified" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  @override
  List<GeneratedColumn> get $columns => [
    opId,
    projectId,
    op,
    state,
    label,
    subject,
    createdAt,
    serverSeq,
    winning,
    reason,
    notified,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'outbox_entries';
  @override
  VerificationContext validateIntegrity(
    Insertable<OutboxEntryRow> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('op_id')) {
      context.handle(
        _opIdMeta,
        opId.isAcceptableOrUnknown(data['op_id']!, _opIdMeta),
      );
    } else if (isInserting) {
      context.missing(_opIdMeta);
    }
    if (data.containsKey('project_id')) {
      context.handle(
        _projectIdMeta,
        projectId.isAcceptableOrUnknown(data['project_id']!, _projectIdMeta),
      );
    } else if (isInserting) {
      context.missing(_projectIdMeta);
    }
    if (data.containsKey('op')) {
      context.handle(_opMeta, op.isAcceptableOrUnknown(data['op']!, _opMeta));
    } else if (isInserting) {
      context.missing(_opMeta);
    }
    if (data.containsKey('state')) {
      context.handle(
        _stateMeta,
        state.isAcceptableOrUnknown(data['state']!, _stateMeta),
      );
    } else if (isInserting) {
      context.missing(_stateMeta);
    }
    if (data.containsKey('label')) {
      context.handle(
        _labelMeta,
        label.isAcceptableOrUnknown(data['label']!, _labelMeta),
      );
    } else if (isInserting) {
      context.missing(_labelMeta);
    }
    if (data.containsKey('subject')) {
      context.handle(
        _subjectMeta,
        subject.isAcceptableOrUnknown(data['subject']!, _subjectMeta),
      );
    }
    if (data.containsKey('created_at')) {
      context.handle(
        _createdAtMeta,
        createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta),
      );
    } else if (isInserting) {
      context.missing(_createdAtMeta);
    }
    if (data.containsKey('server_seq')) {
      context.handle(
        _serverSeqMeta,
        serverSeq.isAcceptableOrUnknown(data['server_seq']!, _serverSeqMeta),
      );
    }
    if (data.containsKey('winning')) {
      context.handle(
        _winningMeta,
        winning.isAcceptableOrUnknown(data['winning']!, _winningMeta),
      );
    }
    if (data.containsKey('reason')) {
      context.handle(
        _reasonMeta,
        reason.isAcceptableOrUnknown(data['reason']!, _reasonMeta),
      );
    }
    if (data.containsKey('notified')) {
      context.handle(
        _notifiedMeta,
        notified.isAcceptableOrUnknown(data['notified']!, _notifiedMeta),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {opId};
  @override
  OutboxEntryRow map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return OutboxEntryRow(
      opId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}op_id'],
      )!,
      projectId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}project_id'],
      )!,
      op: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}op'],
      )!,
      state: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}state'],
      )!,
      label: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}label'],
      )!,
      subject: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}subject'],
      ),
      createdAt: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}created_at'],
      )!,
      serverSeq: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}server_seq'],
      ),
      winning: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}winning'],
      ),
      reason: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}reason'],
      ),
      notified: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}notified'],
      )!,
    );
  }

  @override
  $OutboxEntriesTable createAlias(String alias) {
    return $OutboxEntriesTable(attachedDatabase, alias);
  }
}

class OutboxEntryRow extends DataClass implements Insertable<OutboxEntryRow> {
  final String opId;
  final String projectId;

  /// The `action` operation as sent (JSON), unchanged between tries.
  final String op;

  /// pending, accepted, rejected or failed.
  final String state;

  /// What the person did, as the app lists it ("Floor finish: Oak boards").
  final String label;

  /// The entity the edit concerns, for its badge.
  final String? subject;
  final int createdAt;
  final int? serverSeq;

  /// JSON `[{op_id, server_seq, author, name}]`: the operations that won.
  final String? winning;
  final String? reason;

  /// The rejection notice was shown.
  final bool notified;
  const OutboxEntryRow({
    required this.opId,
    required this.projectId,
    required this.op,
    required this.state,
    required this.label,
    this.subject,
    required this.createdAt,
    this.serverSeq,
    this.winning,
    this.reason,
    required this.notified,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['op_id'] = Variable<String>(opId);
    map['project_id'] = Variable<String>(projectId);
    map['op'] = Variable<String>(op);
    map['state'] = Variable<String>(state);
    map['label'] = Variable<String>(label);
    if (!nullToAbsent || subject != null) {
      map['subject'] = Variable<String>(subject);
    }
    map['created_at'] = Variable<int>(createdAt);
    if (!nullToAbsent || serverSeq != null) {
      map['server_seq'] = Variable<int>(serverSeq);
    }
    if (!nullToAbsent || winning != null) {
      map['winning'] = Variable<String>(winning);
    }
    if (!nullToAbsent || reason != null) {
      map['reason'] = Variable<String>(reason);
    }
    map['notified'] = Variable<bool>(notified);
    return map;
  }

  OutboxEntriesCompanion toCompanion(bool nullToAbsent) {
    return OutboxEntriesCompanion(
      opId: Value(opId),
      projectId: Value(projectId),
      op: Value(op),
      state: Value(state),
      label: Value(label),
      subject: subject == null && nullToAbsent
          ? const Value.absent()
          : Value(subject),
      createdAt: Value(createdAt),
      serverSeq: serverSeq == null && nullToAbsent
          ? const Value.absent()
          : Value(serverSeq),
      winning: winning == null && nullToAbsent
          ? const Value.absent()
          : Value(winning),
      reason: reason == null && nullToAbsent
          ? const Value.absent()
          : Value(reason),
      notified: Value(notified),
    );
  }

  factory OutboxEntryRow.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return OutboxEntryRow(
      opId: serializer.fromJson<String>(json['opId']),
      projectId: serializer.fromJson<String>(json['projectId']),
      op: serializer.fromJson<String>(json['op']),
      state: serializer.fromJson<String>(json['state']),
      label: serializer.fromJson<String>(json['label']),
      subject: serializer.fromJson<String?>(json['subject']),
      createdAt: serializer.fromJson<int>(json['createdAt']),
      serverSeq: serializer.fromJson<int?>(json['serverSeq']),
      winning: serializer.fromJson<String?>(json['winning']),
      reason: serializer.fromJson<String?>(json['reason']),
      notified: serializer.fromJson<bool>(json['notified']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'opId': serializer.toJson<String>(opId),
      'projectId': serializer.toJson<String>(projectId),
      'op': serializer.toJson<String>(op),
      'state': serializer.toJson<String>(state),
      'label': serializer.toJson<String>(label),
      'subject': serializer.toJson<String?>(subject),
      'createdAt': serializer.toJson<int>(createdAt),
      'serverSeq': serializer.toJson<int?>(serverSeq),
      'winning': serializer.toJson<String?>(winning),
      'reason': serializer.toJson<String?>(reason),
      'notified': serializer.toJson<bool>(notified),
    };
  }

  OutboxEntryRow copyWith({
    String? opId,
    String? projectId,
    String? op,
    String? state,
    String? label,
    Value<String?> subject = const Value.absent(),
    int? createdAt,
    Value<int?> serverSeq = const Value.absent(),
    Value<String?> winning = const Value.absent(),
    Value<String?> reason = const Value.absent(),
    bool? notified,
  }) => OutboxEntryRow(
    opId: opId ?? this.opId,
    projectId: projectId ?? this.projectId,
    op: op ?? this.op,
    state: state ?? this.state,
    label: label ?? this.label,
    subject: subject.present ? subject.value : this.subject,
    createdAt: createdAt ?? this.createdAt,
    serverSeq: serverSeq.present ? serverSeq.value : this.serverSeq,
    winning: winning.present ? winning.value : this.winning,
    reason: reason.present ? reason.value : this.reason,
    notified: notified ?? this.notified,
  );
  OutboxEntryRow copyWithCompanion(OutboxEntriesCompanion data) {
    return OutboxEntryRow(
      opId: data.opId.present ? data.opId.value : this.opId,
      projectId: data.projectId.present ? data.projectId.value : this.projectId,
      op: data.op.present ? data.op.value : this.op,
      state: data.state.present ? data.state.value : this.state,
      label: data.label.present ? data.label.value : this.label,
      subject: data.subject.present ? data.subject.value : this.subject,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
      serverSeq: data.serverSeq.present ? data.serverSeq.value : this.serverSeq,
      winning: data.winning.present ? data.winning.value : this.winning,
      reason: data.reason.present ? data.reason.value : this.reason,
      notified: data.notified.present ? data.notified.value : this.notified,
    );
  }

  @override
  String toString() {
    return (StringBuffer('OutboxEntryRow(')
          ..write('opId: $opId, ')
          ..write('projectId: $projectId, ')
          ..write('op: $op, ')
          ..write('state: $state, ')
          ..write('label: $label, ')
          ..write('subject: $subject, ')
          ..write('createdAt: $createdAt, ')
          ..write('serverSeq: $serverSeq, ')
          ..write('winning: $winning, ')
          ..write('reason: $reason, ')
          ..write('notified: $notified')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(
    opId,
    projectId,
    op,
    state,
    label,
    subject,
    createdAt,
    serverSeq,
    winning,
    reason,
    notified,
  );
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is OutboxEntryRow &&
          other.opId == this.opId &&
          other.projectId == this.projectId &&
          other.op == this.op &&
          other.state == this.state &&
          other.label == this.label &&
          other.subject == this.subject &&
          other.createdAt == this.createdAt &&
          other.serverSeq == this.serverSeq &&
          other.winning == this.winning &&
          other.reason == this.reason &&
          other.notified == this.notified);
}

class OutboxEntriesCompanion extends UpdateCompanion<OutboxEntryRow> {
  final Value<String> opId;
  final Value<String> projectId;
  final Value<String> op;
  final Value<String> state;
  final Value<String> label;
  final Value<String?> subject;
  final Value<int> createdAt;
  final Value<int?> serverSeq;
  final Value<String?> winning;
  final Value<String?> reason;
  final Value<bool> notified;
  final Value<int> rowid;
  const OutboxEntriesCompanion({
    this.opId = const Value.absent(),
    this.projectId = const Value.absent(),
    this.op = const Value.absent(),
    this.state = const Value.absent(),
    this.label = const Value.absent(),
    this.subject = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.serverSeq = const Value.absent(),
    this.winning = const Value.absent(),
    this.reason = const Value.absent(),
    this.notified = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  OutboxEntriesCompanion.insert({
    required String opId,
    required String projectId,
    required String op,
    required String state,
    required String label,
    this.subject = const Value.absent(),
    required int createdAt,
    this.serverSeq = const Value.absent(),
    this.winning = const Value.absent(),
    this.reason = const Value.absent(),
    this.notified = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : opId = Value(opId),
       projectId = Value(projectId),
       op = Value(op),
       state = Value(state),
       label = Value(label),
       createdAt = Value(createdAt);
  static Insertable<OutboxEntryRow> custom({
    Expression<String>? opId,
    Expression<String>? projectId,
    Expression<String>? op,
    Expression<String>? state,
    Expression<String>? label,
    Expression<String>? subject,
    Expression<int>? createdAt,
    Expression<int>? serverSeq,
    Expression<String>? winning,
    Expression<String>? reason,
    Expression<bool>? notified,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (opId != null) 'op_id': opId,
      if (projectId != null) 'project_id': projectId,
      if (op != null) 'op': op,
      if (state != null) 'state': state,
      if (label != null) 'label': label,
      if (subject != null) 'subject': subject,
      if (createdAt != null) 'created_at': createdAt,
      if (serverSeq != null) 'server_seq': serverSeq,
      if (winning != null) 'winning': winning,
      if (reason != null) 'reason': reason,
      if (notified != null) 'notified': notified,
      if (rowid != null) 'rowid': rowid,
    });
  }

  OutboxEntriesCompanion copyWith({
    Value<String>? opId,
    Value<String>? projectId,
    Value<String>? op,
    Value<String>? state,
    Value<String>? label,
    Value<String?>? subject,
    Value<int>? createdAt,
    Value<int?>? serverSeq,
    Value<String?>? winning,
    Value<String?>? reason,
    Value<bool>? notified,
    Value<int>? rowid,
  }) {
    return OutboxEntriesCompanion(
      opId: opId ?? this.opId,
      projectId: projectId ?? this.projectId,
      op: op ?? this.op,
      state: state ?? this.state,
      label: label ?? this.label,
      subject: subject ?? this.subject,
      createdAt: createdAt ?? this.createdAt,
      serverSeq: serverSeq ?? this.serverSeq,
      winning: winning ?? this.winning,
      reason: reason ?? this.reason,
      notified: notified ?? this.notified,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (opId.present) {
      map['op_id'] = Variable<String>(opId.value);
    }
    if (projectId.present) {
      map['project_id'] = Variable<String>(projectId.value);
    }
    if (op.present) {
      map['op'] = Variable<String>(op.value);
    }
    if (state.present) {
      map['state'] = Variable<String>(state.value);
    }
    if (label.present) {
      map['label'] = Variable<String>(label.value);
    }
    if (subject.present) {
      map['subject'] = Variable<String>(subject.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<int>(createdAt.value);
    }
    if (serverSeq.present) {
      map['server_seq'] = Variable<int>(serverSeq.value);
    }
    if (winning.present) {
      map['winning'] = Variable<String>(winning.value);
    }
    if (reason.present) {
      map['reason'] = Variable<String>(reason.value);
    }
    if (notified.present) {
      map['notified'] = Variable<bool>(notified.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('OutboxEntriesCompanion(')
          ..write('opId: $opId, ')
          ..write('projectId: $projectId, ')
          ..write('op: $op, ')
          ..write('state: $state, ')
          ..write('label: $label, ')
          ..write('subject: $subject, ')
          ..write('createdAt: $createdAt, ')
          ..write('serverSeq: $serverSeq, ')
          ..write('winning: $winning, ')
          ..write('reason: $reason, ')
          ..write('notified: $notified, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $DigestsTable extends Digests with TableInfo<$DigestsTable, Digest> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $DigestsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _projectIdMeta = const VerificationMeta(
    'projectId',
  );
  @override
  late final GeneratedColumn<String> projectId = GeneratedColumn<String>(
    'project_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _snapshotIdMeta = const VerificationMeta(
    'snapshotId',
  );
  @override
  late final GeneratedColumn<String> snapshotId = GeneratedColumn<String>(
    'snapshot_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _atSeqMeta = const VerificationMeta('atSeq');
  @override
  late final GeneratedColumn<int> atSeq = GeneratedColumn<int>(
    'at_seq',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _createdAtMeta = const VerificationMeta(
    'createdAt',
  );
  @override
  late final GeneratedColumn<String> createdAt = GeneratedColumn<String>(
    'created_at',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _sha256Meta = const VerificationMeta('sha256');
  @override
  late final GeneratedColumn<String> sha256 = GeneratedColumn<String>(
    'sha256',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _bodyMeta = const VerificationMeta('body');
  @override
  late final GeneratedColumn<String> body = GeneratedColumn<String>(
    'body',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [
    projectId,
    snapshotId,
    atSeq,
    createdAt,
    sha256,
    body,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'digests';
  @override
  VerificationContext validateIntegrity(
    Insertable<Digest> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('project_id')) {
      context.handle(
        _projectIdMeta,
        projectId.isAcceptableOrUnknown(data['project_id']!, _projectIdMeta),
      );
    } else if (isInserting) {
      context.missing(_projectIdMeta);
    }
    if (data.containsKey('snapshot_id')) {
      context.handle(
        _snapshotIdMeta,
        snapshotId.isAcceptableOrUnknown(data['snapshot_id']!, _snapshotIdMeta),
      );
    } else if (isInserting) {
      context.missing(_snapshotIdMeta);
    }
    if (data.containsKey('at_seq')) {
      context.handle(
        _atSeqMeta,
        atSeq.isAcceptableOrUnknown(data['at_seq']!, _atSeqMeta),
      );
    } else if (isInserting) {
      context.missing(_atSeqMeta);
    }
    if (data.containsKey('created_at')) {
      context.handle(
        _createdAtMeta,
        createdAt.isAcceptableOrUnknown(data['created_at']!, _createdAtMeta),
      );
    } else if (isInserting) {
      context.missing(_createdAtMeta);
    }
    if (data.containsKey('sha256')) {
      context.handle(
        _sha256Meta,
        sha256.isAcceptableOrUnknown(data['sha256']!, _sha256Meta),
      );
    } else if (isInserting) {
      context.missing(_sha256Meta);
    }
    if (data.containsKey('body')) {
      context.handle(
        _bodyMeta,
        body.isAcceptableOrUnknown(data['body']!, _bodyMeta),
      );
    } else if (isInserting) {
      context.missing(_bodyMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {projectId};
  @override
  Digest map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Digest(
      projectId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}project_id'],
      )!,
      snapshotId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}snapshot_id'],
      )!,
      atSeq: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}at_seq'],
      )!,
      createdAt: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}created_at'],
      )!,
      sha256: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}sha256'],
      )!,
      body: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}body'],
      )!,
    );
  }

  @override
  $DigestsTable createAlias(String alias) {
    return $DigestsTable(attachedDatabase, alias);
  }
}

class Digest extends DataClass implements Insertable<Digest> {
  final String projectId;
  final String snapshotId;
  final int atSeq;
  final String createdAt;
  final String sha256;
  final String body;
  const Digest({
    required this.projectId,
    required this.snapshotId,
    required this.atSeq,
    required this.createdAt,
    required this.sha256,
    required this.body,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['project_id'] = Variable<String>(projectId);
    map['snapshot_id'] = Variable<String>(snapshotId);
    map['at_seq'] = Variable<int>(atSeq);
    map['created_at'] = Variable<String>(createdAt);
    map['sha256'] = Variable<String>(sha256);
    map['body'] = Variable<String>(body);
    return map;
  }

  DigestsCompanion toCompanion(bool nullToAbsent) {
    return DigestsCompanion(
      projectId: Value(projectId),
      snapshotId: Value(snapshotId),
      atSeq: Value(atSeq),
      createdAt: Value(createdAt),
      sha256: Value(sha256),
      body: Value(body),
    );
  }

  factory Digest.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Digest(
      projectId: serializer.fromJson<String>(json['projectId']),
      snapshotId: serializer.fromJson<String>(json['snapshotId']),
      atSeq: serializer.fromJson<int>(json['atSeq']),
      createdAt: serializer.fromJson<String>(json['createdAt']),
      sha256: serializer.fromJson<String>(json['sha256']),
      body: serializer.fromJson<String>(json['body']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'projectId': serializer.toJson<String>(projectId),
      'snapshotId': serializer.toJson<String>(snapshotId),
      'atSeq': serializer.toJson<int>(atSeq),
      'createdAt': serializer.toJson<String>(createdAt),
      'sha256': serializer.toJson<String>(sha256),
      'body': serializer.toJson<String>(body),
    };
  }

  Digest copyWith({
    String? projectId,
    String? snapshotId,
    int? atSeq,
    String? createdAt,
    String? sha256,
    String? body,
  }) => Digest(
    projectId: projectId ?? this.projectId,
    snapshotId: snapshotId ?? this.snapshotId,
    atSeq: atSeq ?? this.atSeq,
    createdAt: createdAt ?? this.createdAt,
    sha256: sha256 ?? this.sha256,
    body: body ?? this.body,
  );
  Digest copyWithCompanion(DigestsCompanion data) {
    return Digest(
      projectId: data.projectId.present ? data.projectId.value : this.projectId,
      snapshotId: data.snapshotId.present
          ? data.snapshotId.value
          : this.snapshotId,
      atSeq: data.atSeq.present ? data.atSeq.value : this.atSeq,
      createdAt: data.createdAt.present ? data.createdAt.value : this.createdAt,
      sha256: data.sha256.present ? data.sha256.value : this.sha256,
      body: data.body.present ? data.body.value : this.body,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Digest(')
          ..write('projectId: $projectId, ')
          ..write('snapshotId: $snapshotId, ')
          ..write('atSeq: $atSeq, ')
          ..write('createdAt: $createdAt, ')
          ..write('sha256: $sha256, ')
          ..write('body: $body')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(projectId, snapshotId, atSeq, createdAt, sha256, body);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Digest &&
          other.projectId == this.projectId &&
          other.snapshotId == this.snapshotId &&
          other.atSeq == this.atSeq &&
          other.createdAt == this.createdAt &&
          other.sha256 == this.sha256 &&
          other.body == this.body);
}

class DigestsCompanion extends UpdateCompanion<Digest> {
  final Value<String> projectId;
  final Value<String> snapshotId;
  final Value<int> atSeq;
  final Value<String> createdAt;
  final Value<String> sha256;
  final Value<String> body;
  final Value<int> rowid;
  const DigestsCompanion({
    this.projectId = const Value.absent(),
    this.snapshotId = const Value.absent(),
    this.atSeq = const Value.absent(),
    this.createdAt = const Value.absent(),
    this.sha256 = const Value.absent(),
    this.body = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  DigestsCompanion.insert({
    required String projectId,
    required String snapshotId,
    required int atSeq,
    required String createdAt,
    required String sha256,
    required String body,
    this.rowid = const Value.absent(),
  }) : projectId = Value(projectId),
       snapshotId = Value(snapshotId),
       atSeq = Value(atSeq),
       createdAt = Value(createdAt),
       sha256 = Value(sha256),
       body = Value(body);
  static Insertable<Digest> custom({
    Expression<String>? projectId,
    Expression<String>? snapshotId,
    Expression<int>? atSeq,
    Expression<String>? createdAt,
    Expression<String>? sha256,
    Expression<String>? body,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (projectId != null) 'project_id': projectId,
      if (snapshotId != null) 'snapshot_id': snapshotId,
      if (atSeq != null) 'at_seq': atSeq,
      if (createdAt != null) 'created_at': createdAt,
      if (sha256 != null) 'sha256': sha256,
      if (body != null) 'body': body,
      if (rowid != null) 'rowid': rowid,
    });
  }

  DigestsCompanion copyWith({
    Value<String>? projectId,
    Value<String>? snapshotId,
    Value<int>? atSeq,
    Value<String>? createdAt,
    Value<String>? sha256,
    Value<String>? body,
    Value<int>? rowid,
  }) {
    return DigestsCompanion(
      projectId: projectId ?? this.projectId,
      snapshotId: snapshotId ?? this.snapshotId,
      atSeq: atSeq ?? this.atSeq,
      createdAt: createdAt ?? this.createdAt,
      sha256: sha256 ?? this.sha256,
      body: body ?? this.body,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (projectId.present) {
      map['project_id'] = Variable<String>(projectId.value);
    }
    if (snapshotId.present) {
      map['snapshot_id'] = Variable<String>(snapshotId.value);
    }
    if (atSeq.present) {
      map['at_seq'] = Variable<int>(atSeq.value);
    }
    if (createdAt.present) {
      map['created_at'] = Variable<String>(createdAt.value);
    }
    if (sha256.present) {
      map['sha256'] = Variable<String>(sha256.value);
    }
    if (body.present) {
      map['body'] = Variable<String>(body.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('DigestsCompanion(')
          ..write('projectId: $projectId, ')
          ..write('snapshotId: $snapshotId, ')
          ..write('atSeq: $atSeq, ')
          ..write('createdAt: $createdAt, ')
          ..write('sha256: $sha256, ')
          ..write('body: $body, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $ManifestsTable extends Manifests
    with TableInfo<$ManifestsTable, Manifest> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $ManifestsTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _projectIdMeta = const VerificationMeta(
    'projectId',
  );
  @override
  late final GeneratedColumn<String> projectId = GeneratedColumn<String>(
    'project_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _setIdMeta = const VerificationMeta('setId');
  @override
  late final GeneratedColumn<String> setId = GeneratedColumn<String>(
    'set_id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _revMeta = const VerificationMeta('rev');
  @override
  late final GeneratedColumn<int> rev = GeneratedColumn<int>(
    'rev',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _atSeqMeta = const VerificationMeta('atSeq');
  @override
  late final GeneratedColumn<int> atSeq = GeneratedColumn<int>(
    'at_seq',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _bodyMeta = const VerificationMeta('body');
  @override
  late final GeneratedColumn<String> body = GeneratedColumn<String>(
    'body',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [projectId, setId, rev, atSeq, body];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'manifests';
  @override
  VerificationContext validateIntegrity(
    Insertable<Manifest> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('project_id')) {
      context.handle(
        _projectIdMeta,
        projectId.isAcceptableOrUnknown(data['project_id']!, _projectIdMeta),
      );
    } else if (isInserting) {
      context.missing(_projectIdMeta);
    }
    if (data.containsKey('set_id')) {
      context.handle(
        _setIdMeta,
        setId.isAcceptableOrUnknown(data['set_id']!, _setIdMeta),
      );
    } else if (isInserting) {
      context.missing(_setIdMeta);
    }
    if (data.containsKey('rev')) {
      context.handle(
        _revMeta,
        rev.isAcceptableOrUnknown(data['rev']!, _revMeta),
      );
    } else if (isInserting) {
      context.missing(_revMeta);
    }
    if (data.containsKey('at_seq')) {
      context.handle(
        _atSeqMeta,
        atSeq.isAcceptableOrUnknown(data['at_seq']!, _atSeqMeta),
      );
    } else if (isInserting) {
      context.missing(_atSeqMeta);
    }
    if (data.containsKey('body')) {
      context.handle(
        _bodyMeta,
        body.isAcceptableOrUnknown(data['body']!, _bodyMeta),
      );
    } else if (isInserting) {
      context.missing(_bodyMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {projectId, setId};
  @override
  Manifest map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Manifest(
      projectId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}project_id'],
      )!,
      setId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}set_id'],
      )!,
      rev: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}rev'],
      )!,
      atSeq: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}at_seq'],
      )!,
      body: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}body'],
      )!,
    );
  }

  @override
  $ManifestsTable createAlias(String alias) {
    return $ManifestsTable(attachedDatabase, alias);
  }
}

class Manifest extends DataClass implements Insertable<Manifest> {
  final String projectId;
  final String setId;
  final int rev;
  final int atSeq;
  final String body;
  const Manifest({
    required this.projectId,
    required this.setId,
    required this.rev,
    required this.atSeq,
    required this.body,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['project_id'] = Variable<String>(projectId);
    map['set_id'] = Variable<String>(setId);
    map['rev'] = Variable<int>(rev);
    map['at_seq'] = Variable<int>(atSeq);
    map['body'] = Variable<String>(body);
    return map;
  }

  ManifestsCompanion toCompanion(bool nullToAbsent) {
    return ManifestsCompanion(
      projectId: Value(projectId),
      setId: Value(setId),
      rev: Value(rev),
      atSeq: Value(atSeq),
      body: Value(body),
    );
  }

  factory Manifest.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Manifest(
      projectId: serializer.fromJson<String>(json['projectId']),
      setId: serializer.fromJson<String>(json['setId']),
      rev: serializer.fromJson<int>(json['rev']),
      atSeq: serializer.fromJson<int>(json['atSeq']),
      body: serializer.fromJson<String>(json['body']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'projectId': serializer.toJson<String>(projectId),
      'setId': serializer.toJson<String>(setId),
      'rev': serializer.toJson<int>(rev),
      'atSeq': serializer.toJson<int>(atSeq),
      'body': serializer.toJson<String>(body),
    };
  }

  Manifest copyWith({
    String? projectId,
    String? setId,
    int? rev,
    int? atSeq,
    String? body,
  }) => Manifest(
    projectId: projectId ?? this.projectId,
    setId: setId ?? this.setId,
    rev: rev ?? this.rev,
    atSeq: atSeq ?? this.atSeq,
    body: body ?? this.body,
  );
  Manifest copyWithCompanion(ManifestsCompanion data) {
    return Manifest(
      projectId: data.projectId.present ? data.projectId.value : this.projectId,
      setId: data.setId.present ? data.setId.value : this.setId,
      rev: data.rev.present ? data.rev.value : this.rev,
      atSeq: data.atSeq.present ? data.atSeq.value : this.atSeq,
      body: data.body.present ? data.body.value : this.body,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Manifest(')
          ..write('projectId: $projectId, ')
          ..write('setId: $setId, ')
          ..write('rev: $rev, ')
          ..write('atSeq: $atSeq, ')
          ..write('body: $body')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(projectId, setId, rev, atSeq, body);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Manifest &&
          other.projectId == this.projectId &&
          other.setId == this.setId &&
          other.rev == this.rev &&
          other.atSeq == this.atSeq &&
          other.body == this.body);
}

class ManifestsCompanion extends UpdateCompanion<Manifest> {
  final Value<String> projectId;
  final Value<String> setId;
  final Value<int> rev;
  final Value<int> atSeq;
  final Value<String> body;
  final Value<int> rowid;
  const ManifestsCompanion({
    this.projectId = const Value.absent(),
    this.setId = const Value.absent(),
    this.rev = const Value.absent(),
    this.atSeq = const Value.absent(),
    this.body = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  ManifestsCompanion.insert({
    required String projectId,
    required String setId,
    required int rev,
    required int atSeq,
    required String body,
    this.rowid = const Value.absent(),
  }) : projectId = Value(projectId),
       setId = Value(setId),
       rev = Value(rev),
       atSeq = Value(atSeq),
       body = Value(body);
  static Insertable<Manifest> custom({
    Expression<String>? projectId,
    Expression<String>? setId,
    Expression<int>? rev,
    Expression<int>? atSeq,
    Expression<String>? body,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (projectId != null) 'project_id': projectId,
      if (setId != null) 'set_id': setId,
      if (rev != null) 'rev': rev,
      if (atSeq != null) 'at_seq': atSeq,
      if (body != null) 'body': body,
      if (rowid != null) 'rowid': rowid,
    });
  }

  ManifestsCompanion copyWith({
    Value<String>? projectId,
    Value<String>? setId,
    Value<int>? rev,
    Value<int>? atSeq,
    Value<String>? body,
    Value<int>? rowid,
  }) {
    return ManifestsCompanion(
      projectId: projectId ?? this.projectId,
      setId: setId ?? this.setId,
      rev: rev ?? this.rev,
      atSeq: atSeq ?? this.atSeq,
      body: body ?? this.body,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (projectId.present) {
      map['project_id'] = Variable<String>(projectId.value);
    }
    if (setId.present) {
      map['set_id'] = Variable<String>(setId.value);
    }
    if (rev.present) {
      map['rev'] = Variable<int>(rev.value);
    }
    if (atSeq.present) {
      map['at_seq'] = Variable<int>(atSeq.value);
    }
    if (body.present) {
      map['body'] = Variable<String>(body.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('ManifestsCompanion(')
          ..write('projectId: $projectId, ')
          ..write('setId: $setId, ')
          ..write('rev: $rev, ')
          ..write('atSeq: $atSeq, ')
          ..write('body: $body, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $TilesTable extends Tiles with TableInfo<$TilesTable, Tile> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $TilesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _shaMeta = const VerificationMeta('sha');
  @override
  late final GeneratedColumn<String> sha = GeneratedColumn<String>(
    'sha',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _bytesMeta = const VerificationMeta('bytes');
  @override
  late final GeneratedColumn<int> bytes = GeneratedColumn<int>(
    'bytes',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _lastUsedMeta = const VerificationMeta(
    'lastUsed',
  );
  @override
  late final GeneratedColumn<int> lastUsed = GeneratedColumn<int>(
    'last_used',
    aliasedName,
    false,
    type: DriftSqlType.int,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [sha, bytes, lastUsed];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'tiles';
  @override
  VerificationContext validateIntegrity(
    Insertable<Tile> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('sha')) {
      context.handle(
        _shaMeta,
        sha.isAcceptableOrUnknown(data['sha']!, _shaMeta),
      );
    } else if (isInserting) {
      context.missing(_shaMeta);
    }
    if (data.containsKey('bytes')) {
      context.handle(
        _bytesMeta,
        bytes.isAcceptableOrUnknown(data['bytes']!, _bytesMeta),
      );
    } else if (isInserting) {
      context.missing(_bytesMeta);
    }
    if (data.containsKey('last_used')) {
      context.handle(
        _lastUsedMeta,
        lastUsed.isAcceptableOrUnknown(data['last_used']!, _lastUsedMeta),
      );
    } else if (isInserting) {
      context.missing(_lastUsedMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {sha};
  @override
  Tile map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Tile(
      sha: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}sha'],
      )!,
      bytes: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}bytes'],
      )!,
      lastUsed: attachedDatabase.typeMapping.read(
        DriftSqlType.int,
        data['${effectivePrefix}last_used'],
      )!,
    );
  }

  @override
  $TilesTable createAlias(String alias) {
    return $TilesTable(attachedDatabase, alias);
  }
}

class Tile extends DataClass implements Insertable<Tile> {
  final String sha;
  final int bytes;
  final int lastUsed;
  const Tile({required this.sha, required this.bytes, required this.lastUsed});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['sha'] = Variable<String>(sha);
    map['bytes'] = Variable<int>(bytes);
    map['last_used'] = Variable<int>(lastUsed);
    return map;
  }

  TilesCompanion toCompanion(bool nullToAbsent) {
    return TilesCompanion(
      sha: Value(sha),
      bytes: Value(bytes),
      lastUsed: Value(lastUsed),
    );
  }

  factory Tile.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Tile(
      sha: serializer.fromJson<String>(json['sha']),
      bytes: serializer.fromJson<int>(json['bytes']),
      lastUsed: serializer.fromJson<int>(json['lastUsed']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'sha': serializer.toJson<String>(sha),
      'bytes': serializer.toJson<int>(bytes),
      'lastUsed': serializer.toJson<int>(lastUsed),
    };
  }

  Tile copyWith({String? sha, int? bytes, int? lastUsed}) => Tile(
    sha: sha ?? this.sha,
    bytes: bytes ?? this.bytes,
    lastUsed: lastUsed ?? this.lastUsed,
  );
  Tile copyWithCompanion(TilesCompanion data) {
    return Tile(
      sha: data.sha.present ? data.sha.value : this.sha,
      bytes: data.bytes.present ? data.bytes.value : this.bytes,
      lastUsed: data.lastUsed.present ? data.lastUsed.value : this.lastUsed,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Tile(')
          ..write('sha: $sha, ')
          ..write('bytes: $bytes, ')
          ..write('lastUsed: $lastUsed')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(sha, bytes, lastUsed);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Tile &&
          other.sha == this.sha &&
          other.bytes == this.bytes &&
          other.lastUsed == this.lastUsed);
}

class TilesCompanion extends UpdateCompanion<Tile> {
  final Value<String> sha;
  final Value<int> bytes;
  final Value<int> lastUsed;
  final Value<int> rowid;
  const TilesCompanion({
    this.sha = const Value.absent(),
    this.bytes = const Value.absent(),
    this.lastUsed = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  TilesCompanion.insert({
    required String sha,
    required int bytes,
    required int lastUsed,
    this.rowid = const Value.absent(),
  }) : sha = Value(sha),
       bytes = Value(bytes),
       lastUsed = Value(lastUsed);
  static Insertable<Tile> custom({
    Expression<String>? sha,
    Expression<int>? bytes,
    Expression<int>? lastUsed,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (sha != null) 'sha': sha,
      if (bytes != null) 'bytes': bytes,
      if (lastUsed != null) 'last_used': lastUsed,
      if (rowid != null) 'rowid': rowid,
    });
  }

  TilesCompanion copyWith({
    Value<String>? sha,
    Value<int>? bytes,
    Value<int>? lastUsed,
    Value<int>? rowid,
  }) {
    return TilesCompanion(
      sha: sha ?? this.sha,
      bytes: bytes ?? this.bytes,
      lastUsed: lastUsed ?? this.lastUsed,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (sha.present) {
      map['sha'] = Variable<String>(sha.value);
    }
    if (bytes.present) {
      map['bytes'] = Variable<int>(bytes.value);
    }
    if (lastUsed.present) {
      map['last_used'] = Variable<int>(lastUsed.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('TilesCompanion(')
          ..write('sha: $sha, ')
          ..write('bytes: $bytes, ')
          ..write('lastUsed: $lastUsed, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

class $KeyValuesTable extends KeyValues
    with TableInfo<$KeyValuesTable, KeyValue> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $KeyValuesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _keyMeta = const VerificationMeta('key');
  @override
  late final GeneratedColumn<String> key = GeneratedColumn<String>(
    'key',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _valueMeta = const VerificationMeta('value');
  @override
  late final GeneratedColumn<String> value = GeneratedColumn<String>(
    'value',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  @override
  List<GeneratedColumn> get $columns => [key, value];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'key_values';
  @override
  VerificationContext validateIntegrity(
    Insertable<KeyValue> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('key')) {
      context.handle(
        _keyMeta,
        key.isAcceptableOrUnknown(data['key']!, _keyMeta),
      );
    } else if (isInserting) {
      context.missing(_keyMeta);
    }
    if (data.containsKey('value')) {
      context.handle(
        _valueMeta,
        value.isAcceptableOrUnknown(data['value']!, _valueMeta),
      );
    } else if (isInserting) {
      context.missing(_valueMeta);
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {key};
  @override
  KeyValue map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return KeyValue(
      key: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}key'],
      )!,
      value: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}value'],
      )!,
    );
  }

  @override
  $KeyValuesTable createAlias(String alias) {
    return $KeyValuesTable(attachedDatabase, alias);
  }
}

class KeyValue extends DataClass implements Insertable<KeyValue> {
  final String key;
  final String value;
  const KeyValue({required this.key, required this.value});
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['key'] = Variable<String>(key);
    map['value'] = Variable<String>(value);
    return map;
  }

  KeyValuesCompanion toCompanion(bool nullToAbsent) {
    return KeyValuesCompanion(key: Value(key), value: Value(value));
  }

  factory KeyValue.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return KeyValue(
      key: serializer.fromJson<String>(json['key']),
      value: serializer.fromJson<String>(json['value']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'key': serializer.toJson<String>(key),
      'value': serializer.toJson<String>(value),
    };
  }

  KeyValue copyWith({String? key, String? value}) =>
      KeyValue(key: key ?? this.key, value: value ?? this.value);
  KeyValue copyWithCompanion(KeyValuesCompanion data) {
    return KeyValue(
      key: data.key.present ? data.key.value : this.key,
      value: data.value.present ? data.value.value : this.value,
    );
  }

  @override
  String toString() {
    return (StringBuffer('KeyValue(')
          ..write('key: $key, ')
          ..write('value: $value')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode => Object.hash(key, value);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is KeyValue && other.key == this.key && other.value == this.value);
}

class KeyValuesCompanion extends UpdateCompanion<KeyValue> {
  final Value<String> key;
  final Value<String> value;
  final Value<int> rowid;
  const KeyValuesCompanion({
    this.key = const Value.absent(),
    this.value = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  KeyValuesCompanion.insert({
    required String key,
    required String value,
    this.rowid = const Value.absent(),
  }) : key = Value(key),
       value = Value(value);
  static Insertable<KeyValue> custom({
    Expression<String>? key,
    Expression<String>? value,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (key != null) 'key': key,
      if (value != null) 'value': value,
      if (rowid != null) 'rowid': rowid,
    });
  }

  KeyValuesCompanion copyWith({
    Value<String>? key,
    Value<String>? value,
    Value<int>? rowid,
  }) {
    return KeyValuesCompanion(
      key: key ?? this.key,
      value: value ?? this.value,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (key.present) {
      map['key'] = Variable<String>(key.value);
    }
    if (value.present) {
      map['value'] = Variable<String>(value.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('KeyValuesCompanion(')
          ..write('key: $key, ')
          ..write('value: $value, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

abstract class _$ReplicaDb extends GeneratedDatabase {
  _$ReplicaDb(QueryExecutor e) : super(e);
  $ReplicaDbManager get managers => $ReplicaDbManager(this);
  late final $ProjectsTable projects = $ProjectsTable(this);
  late final $OpsTable ops = $OpsTable(this);
  late final $OutboxEntriesTable outboxEntries = $OutboxEntriesTable(this);
  late final $DigestsTable digests = $DigestsTable(this);
  late final $ManifestsTable manifests = $ManifestsTable(this);
  late final $TilesTable tiles = $TilesTable(this);
  late final $KeyValuesTable keyValues = $KeyValuesTable(this);
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [
    projects,
    ops,
    outboxEntries,
    digests,
    manifests,
    tiles,
    keyValues,
  ];
}

typedef $$ProjectsTableCreateCompanionBuilder =
    ProjectsCompanion Function({
      required String projectId,
      required String name,
      required String role,
      Value<String?> ownerName,
      Value<int> headSeq,
      Value<int> pulledSeq,
      Value<bool> starred,
      Value<String?> record,
      Value<String?> updatedAt,
      Value<DateTime?> syncedAt,
      Value<String?> setId,
      Value<int> rowid,
    });
typedef $$ProjectsTableUpdateCompanionBuilder =
    ProjectsCompanion Function({
      Value<String> projectId,
      Value<String> name,
      Value<String> role,
      Value<String?> ownerName,
      Value<int> headSeq,
      Value<int> pulledSeq,
      Value<bool> starred,
      Value<String?> record,
      Value<String?> updatedAt,
      Value<DateTime?> syncedAt,
      Value<String?> setId,
      Value<int> rowid,
    });

class $$ProjectsTableFilterComposer
    extends Composer<_$ReplicaDb, $ProjectsTable> {
  $$ProjectsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get projectId => $composableBuilder(
    column: $table.projectId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get role => $composableBuilder(
    column: $table.role,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get ownerName => $composableBuilder(
    column: $table.ownerName,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get headSeq => $composableBuilder(
    column: $table.headSeq,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get pulledSeq => $composableBuilder(
    column: $table.pulledSeq,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get starred => $composableBuilder(
    column: $table.starred,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get record => $composableBuilder(
    column: $table.record,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get syncedAt => $composableBuilder(
    column: $table.syncedAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get setId => $composableBuilder(
    column: $table.setId,
    builder: (column) => ColumnFilters(column),
  );
}

class $$ProjectsTableOrderingComposer
    extends Composer<_$ReplicaDb, $ProjectsTable> {
  $$ProjectsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get projectId => $composableBuilder(
    column: $table.projectId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get role => $composableBuilder(
    column: $table.role,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get ownerName => $composableBuilder(
    column: $table.ownerName,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get headSeq => $composableBuilder(
    column: $table.headSeq,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get pulledSeq => $composableBuilder(
    column: $table.pulledSeq,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get starred => $composableBuilder(
    column: $table.starred,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get record => $composableBuilder(
    column: $table.record,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get updatedAt => $composableBuilder(
    column: $table.updatedAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get syncedAt => $composableBuilder(
    column: $table.syncedAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get setId => $composableBuilder(
    column: $table.setId,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$ProjectsTableAnnotationComposer
    extends Composer<_$ReplicaDb, $ProjectsTable> {
  $$ProjectsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get projectId =>
      $composableBuilder(column: $table.projectId, builder: (column) => column);

  GeneratedColumn<String> get name =>
      $composableBuilder(column: $table.name, builder: (column) => column);

  GeneratedColumn<String> get role =>
      $composableBuilder(column: $table.role, builder: (column) => column);

  GeneratedColumn<String> get ownerName =>
      $composableBuilder(column: $table.ownerName, builder: (column) => column);

  GeneratedColumn<int> get headSeq =>
      $composableBuilder(column: $table.headSeq, builder: (column) => column);

  GeneratedColumn<int> get pulledSeq =>
      $composableBuilder(column: $table.pulledSeq, builder: (column) => column);

  GeneratedColumn<bool> get starred =>
      $composableBuilder(column: $table.starred, builder: (column) => column);

  GeneratedColumn<String> get record =>
      $composableBuilder(column: $table.record, builder: (column) => column);

  GeneratedColumn<String> get updatedAt =>
      $composableBuilder(column: $table.updatedAt, builder: (column) => column);

  GeneratedColumn<DateTime> get syncedAt =>
      $composableBuilder(column: $table.syncedAt, builder: (column) => column);

  GeneratedColumn<String> get setId =>
      $composableBuilder(column: $table.setId, builder: (column) => column);
}

class $$ProjectsTableTableManager
    extends
        RootTableManager<
          _$ReplicaDb,
          $ProjectsTable,
          Project,
          $$ProjectsTableFilterComposer,
          $$ProjectsTableOrderingComposer,
          $$ProjectsTableAnnotationComposer,
          $$ProjectsTableCreateCompanionBuilder,
          $$ProjectsTableUpdateCompanionBuilder,
          (Project, BaseReferences<_$ReplicaDb, $ProjectsTable, Project>),
          Project,
          PrefetchHooks Function()
        > {
  $$ProjectsTableTableManager(_$ReplicaDb db, $ProjectsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ProjectsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ProjectsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ProjectsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> projectId = const Value.absent(),
                Value<String> name = const Value.absent(),
                Value<String> role = const Value.absent(),
                Value<String?> ownerName = const Value.absent(),
                Value<int> headSeq = const Value.absent(),
                Value<int> pulledSeq = const Value.absent(),
                Value<bool> starred = const Value.absent(),
                Value<String?> record = const Value.absent(),
                Value<String?> updatedAt = const Value.absent(),
                Value<DateTime?> syncedAt = const Value.absent(),
                Value<String?> setId = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => ProjectsCompanion(
                projectId: projectId,
                name: name,
                role: role,
                ownerName: ownerName,
                headSeq: headSeq,
                pulledSeq: pulledSeq,
                starred: starred,
                record: record,
                updatedAt: updatedAt,
                syncedAt: syncedAt,
                setId: setId,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String projectId,
                required String name,
                required String role,
                Value<String?> ownerName = const Value.absent(),
                Value<int> headSeq = const Value.absent(),
                Value<int> pulledSeq = const Value.absent(),
                Value<bool> starred = const Value.absent(),
                Value<String?> record = const Value.absent(),
                Value<String?> updatedAt = const Value.absent(),
                Value<DateTime?> syncedAt = const Value.absent(),
                Value<String?> setId = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => ProjectsCompanion.insert(
                projectId: projectId,
                name: name,
                role: role,
                ownerName: ownerName,
                headSeq: headSeq,
                pulledSeq: pulledSeq,
                starred: starred,
                record: record,
                updatedAt: updatedAt,
                syncedAt: syncedAt,
                setId: setId,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$ProjectsTable, Project>(table),
                  BaseReferences<_$ReplicaDb, $ProjectsTable, Project>(
                    db,
                    table,
                    e,
                  ),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$ProjectsTableProcessedTableManager =
    ProcessedTableManager<
      _$ReplicaDb,
      $ProjectsTable,
      Project,
      $$ProjectsTableFilterComposer,
      $$ProjectsTableOrderingComposer,
      $$ProjectsTableAnnotationComposer,
      $$ProjectsTableCreateCompanionBuilder,
      $$ProjectsTableUpdateCompanionBuilder,
      (Project, BaseReferences<_$ReplicaDb, $ProjectsTable, Project>),
      Project,
      PrefetchHooks Function()
    >;
typedef $$OpsTableCreateCompanionBuilder =
    OpsCompanion Function({
      required String projectId,
      required int serverSeq,
      required String opId,
      required String replicaId,
      required String author,
      required String authorKind,
      required String kind,
      required String name,
      required String at,
      required int baseSeq,
      required String touched,
      Value<String?> deltaFormat,
      Value<Uint8List?> delta,
      Value<String?> action,
      Value<String?> restore,
      Value<int> rowid,
    });
typedef $$OpsTableUpdateCompanionBuilder =
    OpsCompanion Function({
      Value<String> projectId,
      Value<int> serverSeq,
      Value<String> opId,
      Value<String> replicaId,
      Value<String> author,
      Value<String> authorKind,
      Value<String> kind,
      Value<String> name,
      Value<String> at,
      Value<int> baseSeq,
      Value<String> touched,
      Value<String?> deltaFormat,
      Value<Uint8List?> delta,
      Value<String?> action,
      Value<String?> restore,
      Value<int> rowid,
    });

class $$OpsTableFilterComposer extends Composer<_$ReplicaDb, $OpsTable> {
  $$OpsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get projectId => $composableBuilder(
    column: $table.projectId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get serverSeq => $composableBuilder(
    column: $table.serverSeq,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get opId => $composableBuilder(
    column: $table.opId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get replicaId => $composableBuilder(
    column: $table.replicaId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get author => $composableBuilder(
    column: $table.author,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get authorKind => $composableBuilder(
    column: $table.authorKind,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get kind => $composableBuilder(
    column: $table.kind,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get at => $composableBuilder(
    column: $table.at,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get baseSeq => $composableBuilder(
    column: $table.baseSeq,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get touched => $composableBuilder(
    column: $table.touched,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get deltaFormat => $composableBuilder(
    column: $table.deltaFormat,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<Uint8List> get delta => $composableBuilder(
    column: $table.delta,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get action => $composableBuilder(
    column: $table.action,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get restore => $composableBuilder(
    column: $table.restore,
    builder: (column) => ColumnFilters(column),
  );
}

class $$OpsTableOrderingComposer extends Composer<_$ReplicaDb, $OpsTable> {
  $$OpsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get projectId => $composableBuilder(
    column: $table.projectId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get serverSeq => $composableBuilder(
    column: $table.serverSeq,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get opId => $composableBuilder(
    column: $table.opId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get replicaId => $composableBuilder(
    column: $table.replicaId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get author => $composableBuilder(
    column: $table.author,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get authorKind => $composableBuilder(
    column: $table.authorKind,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get kind => $composableBuilder(
    column: $table.kind,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get name => $composableBuilder(
    column: $table.name,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get at => $composableBuilder(
    column: $table.at,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get baseSeq => $composableBuilder(
    column: $table.baseSeq,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get touched => $composableBuilder(
    column: $table.touched,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get deltaFormat => $composableBuilder(
    column: $table.deltaFormat,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<Uint8List> get delta => $composableBuilder(
    column: $table.delta,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get action => $composableBuilder(
    column: $table.action,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get restore => $composableBuilder(
    column: $table.restore,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$OpsTableAnnotationComposer extends Composer<_$ReplicaDb, $OpsTable> {
  $$OpsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get projectId =>
      $composableBuilder(column: $table.projectId, builder: (column) => column);

  GeneratedColumn<int> get serverSeq =>
      $composableBuilder(column: $table.serverSeq, builder: (column) => column);

  GeneratedColumn<String> get opId =>
      $composableBuilder(column: $table.opId, builder: (column) => column);

  GeneratedColumn<String> get replicaId =>
      $composableBuilder(column: $table.replicaId, builder: (column) => column);

  GeneratedColumn<String> get author =>
      $composableBuilder(column: $table.author, builder: (column) => column);

  GeneratedColumn<String> get authorKind => $composableBuilder(
    column: $table.authorKind,
    builder: (column) => column,
  );

  GeneratedColumn<String> get kind =>
      $composableBuilder(column: $table.kind, builder: (column) => column);

  GeneratedColumn<String> get name =>
      $composableBuilder(column: $table.name, builder: (column) => column);

  GeneratedColumn<String> get at =>
      $composableBuilder(column: $table.at, builder: (column) => column);

  GeneratedColumn<int> get baseSeq =>
      $composableBuilder(column: $table.baseSeq, builder: (column) => column);

  GeneratedColumn<String> get touched =>
      $composableBuilder(column: $table.touched, builder: (column) => column);

  GeneratedColumn<String> get deltaFormat => $composableBuilder(
    column: $table.deltaFormat,
    builder: (column) => column,
  );

  GeneratedColumn<Uint8List> get delta =>
      $composableBuilder(column: $table.delta, builder: (column) => column);

  GeneratedColumn<String> get action =>
      $composableBuilder(column: $table.action, builder: (column) => column);

  GeneratedColumn<String> get restore =>
      $composableBuilder(column: $table.restore, builder: (column) => column);
}

class $$OpsTableTableManager
    extends
        RootTableManager<
          _$ReplicaDb,
          $OpsTable,
          Op,
          $$OpsTableFilterComposer,
          $$OpsTableOrderingComposer,
          $$OpsTableAnnotationComposer,
          $$OpsTableCreateCompanionBuilder,
          $$OpsTableUpdateCompanionBuilder,
          (Op, BaseReferences<_$ReplicaDb, $OpsTable, Op>),
          Op,
          PrefetchHooks Function()
        > {
  $$OpsTableTableManager(_$ReplicaDb db, $OpsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$OpsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$OpsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$OpsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> projectId = const Value.absent(),
                Value<int> serverSeq = const Value.absent(),
                Value<String> opId = const Value.absent(),
                Value<String> replicaId = const Value.absent(),
                Value<String> author = const Value.absent(),
                Value<String> authorKind = const Value.absent(),
                Value<String> kind = const Value.absent(),
                Value<String> name = const Value.absent(),
                Value<String> at = const Value.absent(),
                Value<int> baseSeq = const Value.absent(),
                Value<String> touched = const Value.absent(),
                Value<String?> deltaFormat = const Value.absent(),
                Value<Uint8List?> delta = const Value.absent(),
                Value<String?> action = const Value.absent(),
                Value<String?> restore = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => OpsCompanion(
                projectId: projectId,
                serverSeq: serverSeq,
                opId: opId,
                replicaId: replicaId,
                author: author,
                authorKind: authorKind,
                kind: kind,
                name: name,
                at: at,
                baseSeq: baseSeq,
                touched: touched,
                deltaFormat: deltaFormat,
                delta: delta,
                action: action,
                restore: restore,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String projectId,
                required int serverSeq,
                required String opId,
                required String replicaId,
                required String author,
                required String authorKind,
                required String kind,
                required String name,
                required String at,
                required int baseSeq,
                required String touched,
                Value<String?> deltaFormat = const Value.absent(),
                Value<Uint8List?> delta = const Value.absent(),
                Value<String?> action = const Value.absent(),
                Value<String?> restore = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => OpsCompanion.insert(
                projectId: projectId,
                serverSeq: serverSeq,
                opId: opId,
                replicaId: replicaId,
                author: author,
                authorKind: authorKind,
                kind: kind,
                name: name,
                at: at,
                baseSeq: baseSeq,
                touched: touched,
                deltaFormat: deltaFormat,
                delta: delta,
                action: action,
                restore: restore,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$OpsTable, Op>(table),
                  BaseReferences<_$ReplicaDb, $OpsTable, Op>(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$OpsTableProcessedTableManager =
    ProcessedTableManager<
      _$ReplicaDb,
      $OpsTable,
      Op,
      $$OpsTableFilterComposer,
      $$OpsTableOrderingComposer,
      $$OpsTableAnnotationComposer,
      $$OpsTableCreateCompanionBuilder,
      $$OpsTableUpdateCompanionBuilder,
      (Op, BaseReferences<_$ReplicaDb, $OpsTable, Op>),
      Op,
      PrefetchHooks Function()
    >;
typedef $$OutboxEntriesTableCreateCompanionBuilder =
    OutboxEntriesCompanion Function({
      required String opId,
      required String projectId,
      required String op,
      required String state,
      required String label,
      Value<String?> subject,
      required int createdAt,
      Value<int?> serverSeq,
      Value<String?> winning,
      Value<String?> reason,
      Value<bool> notified,
      Value<int> rowid,
    });
typedef $$OutboxEntriesTableUpdateCompanionBuilder =
    OutboxEntriesCompanion Function({
      Value<String> opId,
      Value<String> projectId,
      Value<String> op,
      Value<String> state,
      Value<String> label,
      Value<String?> subject,
      Value<int> createdAt,
      Value<int?> serverSeq,
      Value<String?> winning,
      Value<String?> reason,
      Value<bool> notified,
      Value<int> rowid,
    });

class $$OutboxEntriesTableFilterComposer
    extends Composer<_$ReplicaDb, $OutboxEntriesTable> {
  $$OutboxEntriesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get opId => $composableBuilder(
    column: $table.opId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get projectId => $composableBuilder(
    column: $table.projectId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get op => $composableBuilder(
    column: $table.op,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get state => $composableBuilder(
    column: $table.state,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get label => $composableBuilder(
    column: $table.label,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get subject => $composableBuilder(
    column: $table.subject,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get serverSeq => $composableBuilder(
    column: $table.serverSeq,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get winning => $composableBuilder(
    column: $table.winning,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get reason => $composableBuilder(
    column: $table.reason,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get notified => $composableBuilder(
    column: $table.notified,
    builder: (column) => ColumnFilters(column),
  );
}

class $$OutboxEntriesTableOrderingComposer
    extends Composer<_$ReplicaDb, $OutboxEntriesTable> {
  $$OutboxEntriesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get opId => $composableBuilder(
    column: $table.opId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get projectId => $composableBuilder(
    column: $table.projectId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get op => $composableBuilder(
    column: $table.op,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get state => $composableBuilder(
    column: $table.state,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get label => $composableBuilder(
    column: $table.label,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get subject => $composableBuilder(
    column: $table.subject,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get serverSeq => $composableBuilder(
    column: $table.serverSeq,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get winning => $composableBuilder(
    column: $table.winning,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get reason => $composableBuilder(
    column: $table.reason,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get notified => $composableBuilder(
    column: $table.notified,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$OutboxEntriesTableAnnotationComposer
    extends Composer<_$ReplicaDb, $OutboxEntriesTable> {
  $$OutboxEntriesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get opId =>
      $composableBuilder(column: $table.opId, builder: (column) => column);

  GeneratedColumn<String> get projectId =>
      $composableBuilder(column: $table.projectId, builder: (column) => column);

  GeneratedColumn<String> get op =>
      $composableBuilder(column: $table.op, builder: (column) => column);

  GeneratedColumn<String> get state =>
      $composableBuilder(column: $table.state, builder: (column) => column);

  GeneratedColumn<String> get label =>
      $composableBuilder(column: $table.label, builder: (column) => column);

  GeneratedColumn<String> get subject =>
      $composableBuilder(column: $table.subject, builder: (column) => column);

  GeneratedColumn<int> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);

  GeneratedColumn<int> get serverSeq =>
      $composableBuilder(column: $table.serverSeq, builder: (column) => column);

  GeneratedColumn<String> get winning =>
      $composableBuilder(column: $table.winning, builder: (column) => column);

  GeneratedColumn<String> get reason =>
      $composableBuilder(column: $table.reason, builder: (column) => column);

  GeneratedColumn<bool> get notified =>
      $composableBuilder(column: $table.notified, builder: (column) => column);
}

class $$OutboxEntriesTableTableManager
    extends
        RootTableManager<
          _$ReplicaDb,
          $OutboxEntriesTable,
          OutboxEntryRow,
          $$OutboxEntriesTableFilterComposer,
          $$OutboxEntriesTableOrderingComposer,
          $$OutboxEntriesTableAnnotationComposer,
          $$OutboxEntriesTableCreateCompanionBuilder,
          $$OutboxEntriesTableUpdateCompanionBuilder,
          (
            OutboxEntryRow,
            BaseReferences<_$ReplicaDb, $OutboxEntriesTable, OutboxEntryRow>,
          ),
          OutboxEntryRow,
          PrefetchHooks Function()
        > {
  $$OutboxEntriesTableTableManager(_$ReplicaDb db, $OutboxEntriesTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$OutboxEntriesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$OutboxEntriesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$OutboxEntriesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> opId = const Value.absent(),
                Value<String> projectId = const Value.absent(),
                Value<String> op = const Value.absent(),
                Value<String> state = const Value.absent(),
                Value<String> label = const Value.absent(),
                Value<String?> subject = const Value.absent(),
                Value<int> createdAt = const Value.absent(),
                Value<int?> serverSeq = const Value.absent(),
                Value<String?> winning = const Value.absent(),
                Value<String?> reason = const Value.absent(),
                Value<bool> notified = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => OutboxEntriesCompanion(
                opId: opId,
                projectId: projectId,
                op: op,
                state: state,
                label: label,
                subject: subject,
                createdAt: createdAt,
                serverSeq: serverSeq,
                winning: winning,
                reason: reason,
                notified: notified,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String opId,
                required String projectId,
                required String op,
                required String state,
                required String label,
                Value<String?> subject = const Value.absent(),
                required int createdAt,
                Value<int?> serverSeq = const Value.absent(),
                Value<String?> winning = const Value.absent(),
                Value<String?> reason = const Value.absent(),
                Value<bool> notified = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => OutboxEntriesCompanion.insert(
                opId: opId,
                projectId: projectId,
                op: op,
                state: state,
                label: label,
                subject: subject,
                createdAt: createdAt,
                serverSeq: serverSeq,
                winning: winning,
                reason: reason,
                notified: notified,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$OutboxEntriesTable, OutboxEntryRow>(table),
                  BaseReferences<
                    _$ReplicaDb,
                    $OutboxEntriesTable,
                    OutboxEntryRow
                  >(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$OutboxEntriesTableProcessedTableManager =
    ProcessedTableManager<
      _$ReplicaDb,
      $OutboxEntriesTable,
      OutboxEntryRow,
      $$OutboxEntriesTableFilterComposer,
      $$OutboxEntriesTableOrderingComposer,
      $$OutboxEntriesTableAnnotationComposer,
      $$OutboxEntriesTableCreateCompanionBuilder,
      $$OutboxEntriesTableUpdateCompanionBuilder,
      (
        OutboxEntryRow,
        BaseReferences<_$ReplicaDb, $OutboxEntriesTable, OutboxEntryRow>,
      ),
      OutboxEntryRow,
      PrefetchHooks Function()
    >;
typedef $$DigestsTableCreateCompanionBuilder =
    DigestsCompanion Function({
      required String projectId,
      required String snapshotId,
      required int atSeq,
      required String createdAt,
      required String sha256,
      required String body,
      Value<int> rowid,
    });
typedef $$DigestsTableUpdateCompanionBuilder =
    DigestsCompanion Function({
      Value<String> projectId,
      Value<String> snapshotId,
      Value<int> atSeq,
      Value<String> createdAt,
      Value<String> sha256,
      Value<String> body,
      Value<int> rowid,
    });

class $$DigestsTableFilterComposer
    extends Composer<_$ReplicaDb, $DigestsTable> {
  $$DigestsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get projectId => $composableBuilder(
    column: $table.projectId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get snapshotId => $composableBuilder(
    column: $table.snapshotId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get atSeq => $composableBuilder(
    column: $table.atSeq,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get sha256 => $composableBuilder(
    column: $table.sha256,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get body => $composableBuilder(
    column: $table.body,
    builder: (column) => ColumnFilters(column),
  );
}

class $$DigestsTableOrderingComposer
    extends Composer<_$ReplicaDb, $DigestsTable> {
  $$DigestsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get projectId => $composableBuilder(
    column: $table.projectId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get snapshotId => $composableBuilder(
    column: $table.snapshotId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get atSeq => $composableBuilder(
    column: $table.atSeq,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get createdAt => $composableBuilder(
    column: $table.createdAt,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get sha256 => $composableBuilder(
    column: $table.sha256,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get body => $composableBuilder(
    column: $table.body,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$DigestsTableAnnotationComposer
    extends Composer<_$ReplicaDb, $DigestsTable> {
  $$DigestsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get projectId =>
      $composableBuilder(column: $table.projectId, builder: (column) => column);

  GeneratedColumn<String> get snapshotId => $composableBuilder(
    column: $table.snapshotId,
    builder: (column) => column,
  );

  GeneratedColumn<int> get atSeq =>
      $composableBuilder(column: $table.atSeq, builder: (column) => column);

  GeneratedColumn<String> get createdAt =>
      $composableBuilder(column: $table.createdAt, builder: (column) => column);

  GeneratedColumn<String> get sha256 =>
      $composableBuilder(column: $table.sha256, builder: (column) => column);

  GeneratedColumn<String> get body =>
      $composableBuilder(column: $table.body, builder: (column) => column);
}

class $$DigestsTableTableManager
    extends
        RootTableManager<
          _$ReplicaDb,
          $DigestsTable,
          Digest,
          $$DigestsTableFilterComposer,
          $$DigestsTableOrderingComposer,
          $$DigestsTableAnnotationComposer,
          $$DigestsTableCreateCompanionBuilder,
          $$DigestsTableUpdateCompanionBuilder,
          (Digest, BaseReferences<_$ReplicaDb, $DigestsTable, Digest>),
          Digest,
          PrefetchHooks Function()
        > {
  $$DigestsTableTableManager(_$ReplicaDb db, $DigestsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$DigestsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$DigestsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$DigestsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> projectId = const Value.absent(),
                Value<String> snapshotId = const Value.absent(),
                Value<int> atSeq = const Value.absent(),
                Value<String> createdAt = const Value.absent(),
                Value<String> sha256 = const Value.absent(),
                Value<String> body = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => DigestsCompanion(
                projectId: projectId,
                snapshotId: snapshotId,
                atSeq: atSeq,
                createdAt: createdAt,
                sha256: sha256,
                body: body,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String projectId,
                required String snapshotId,
                required int atSeq,
                required String createdAt,
                required String sha256,
                required String body,
                Value<int> rowid = const Value.absent(),
              }) => DigestsCompanion.insert(
                projectId: projectId,
                snapshotId: snapshotId,
                atSeq: atSeq,
                createdAt: createdAt,
                sha256: sha256,
                body: body,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$DigestsTable, Digest>(table),
                  BaseReferences<_$ReplicaDb, $DigestsTable, Digest>(
                    db,
                    table,
                    e,
                  ),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$DigestsTableProcessedTableManager =
    ProcessedTableManager<
      _$ReplicaDb,
      $DigestsTable,
      Digest,
      $$DigestsTableFilterComposer,
      $$DigestsTableOrderingComposer,
      $$DigestsTableAnnotationComposer,
      $$DigestsTableCreateCompanionBuilder,
      $$DigestsTableUpdateCompanionBuilder,
      (Digest, BaseReferences<_$ReplicaDb, $DigestsTable, Digest>),
      Digest,
      PrefetchHooks Function()
    >;
typedef $$ManifestsTableCreateCompanionBuilder =
    ManifestsCompanion Function({
      required String projectId,
      required String setId,
      required int rev,
      required int atSeq,
      required String body,
      Value<int> rowid,
    });
typedef $$ManifestsTableUpdateCompanionBuilder =
    ManifestsCompanion Function({
      Value<String> projectId,
      Value<String> setId,
      Value<int> rev,
      Value<int> atSeq,
      Value<String> body,
      Value<int> rowid,
    });

class $$ManifestsTableFilterComposer
    extends Composer<_$ReplicaDb, $ManifestsTable> {
  $$ManifestsTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get projectId => $composableBuilder(
    column: $table.projectId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get setId => $composableBuilder(
    column: $table.setId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get rev => $composableBuilder(
    column: $table.rev,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get atSeq => $composableBuilder(
    column: $table.atSeq,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get body => $composableBuilder(
    column: $table.body,
    builder: (column) => ColumnFilters(column),
  );
}

class $$ManifestsTableOrderingComposer
    extends Composer<_$ReplicaDb, $ManifestsTable> {
  $$ManifestsTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get projectId => $composableBuilder(
    column: $table.projectId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get setId => $composableBuilder(
    column: $table.setId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get rev => $composableBuilder(
    column: $table.rev,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get atSeq => $composableBuilder(
    column: $table.atSeq,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get body => $composableBuilder(
    column: $table.body,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$ManifestsTableAnnotationComposer
    extends Composer<_$ReplicaDb, $ManifestsTable> {
  $$ManifestsTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get projectId =>
      $composableBuilder(column: $table.projectId, builder: (column) => column);

  GeneratedColumn<String> get setId =>
      $composableBuilder(column: $table.setId, builder: (column) => column);

  GeneratedColumn<int> get rev =>
      $composableBuilder(column: $table.rev, builder: (column) => column);

  GeneratedColumn<int> get atSeq =>
      $composableBuilder(column: $table.atSeq, builder: (column) => column);

  GeneratedColumn<String> get body =>
      $composableBuilder(column: $table.body, builder: (column) => column);
}

class $$ManifestsTableTableManager
    extends
        RootTableManager<
          _$ReplicaDb,
          $ManifestsTable,
          Manifest,
          $$ManifestsTableFilterComposer,
          $$ManifestsTableOrderingComposer,
          $$ManifestsTableAnnotationComposer,
          $$ManifestsTableCreateCompanionBuilder,
          $$ManifestsTableUpdateCompanionBuilder,
          (Manifest, BaseReferences<_$ReplicaDb, $ManifestsTable, Manifest>),
          Manifest,
          PrefetchHooks Function()
        > {
  $$ManifestsTableTableManager(_$ReplicaDb db, $ManifestsTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$ManifestsTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$ManifestsTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$ManifestsTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> projectId = const Value.absent(),
                Value<String> setId = const Value.absent(),
                Value<int> rev = const Value.absent(),
                Value<int> atSeq = const Value.absent(),
                Value<String> body = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => ManifestsCompanion(
                projectId: projectId,
                setId: setId,
                rev: rev,
                atSeq: atSeq,
                body: body,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String projectId,
                required String setId,
                required int rev,
                required int atSeq,
                required String body,
                Value<int> rowid = const Value.absent(),
              }) => ManifestsCompanion.insert(
                projectId: projectId,
                setId: setId,
                rev: rev,
                atSeq: atSeq,
                body: body,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$ManifestsTable, Manifest>(table),
                  BaseReferences<_$ReplicaDb, $ManifestsTable, Manifest>(
                    db,
                    table,
                    e,
                  ),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$ManifestsTableProcessedTableManager =
    ProcessedTableManager<
      _$ReplicaDb,
      $ManifestsTable,
      Manifest,
      $$ManifestsTableFilterComposer,
      $$ManifestsTableOrderingComposer,
      $$ManifestsTableAnnotationComposer,
      $$ManifestsTableCreateCompanionBuilder,
      $$ManifestsTableUpdateCompanionBuilder,
      (Manifest, BaseReferences<_$ReplicaDb, $ManifestsTable, Manifest>),
      Manifest,
      PrefetchHooks Function()
    >;
typedef $$TilesTableCreateCompanionBuilder =
    TilesCompanion Function({
      required String sha,
      required int bytes,
      required int lastUsed,
      Value<int> rowid,
    });
typedef $$TilesTableUpdateCompanionBuilder =
    TilesCompanion Function({
      Value<String> sha,
      Value<int> bytes,
      Value<int> lastUsed,
      Value<int> rowid,
    });

class $$TilesTableFilterComposer extends Composer<_$ReplicaDb, $TilesTable> {
  $$TilesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get sha => $composableBuilder(
    column: $table.sha,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get bytes => $composableBuilder(
    column: $table.bytes,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<int> get lastUsed => $composableBuilder(
    column: $table.lastUsed,
    builder: (column) => ColumnFilters(column),
  );
}

class $$TilesTableOrderingComposer extends Composer<_$ReplicaDb, $TilesTable> {
  $$TilesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get sha => $composableBuilder(
    column: $table.sha,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get bytes => $composableBuilder(
    column: $table.bytes,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<int> get lastUsed => $composableBuilder(
    column: $table.lastUsed,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$TilesTableAnnotationComposer
    extends Composer<_$ReplicaDb, $TilesTable> {
  $$TilesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get sha =>
      $composableBuilder(column: $table.sha, builder: (column) => column);

  GeneratedColumn<int> get bytes =>
      $composableBuilder(column: $table.bytes, builder: (column) => column);

  GeneratedColumn<int> get lastUsed =>
      $composableBuilder(column: $table.lastUsed, builder: (column) => column);
}

class $$TilesTableTableManager
    extends
        RootTableManager<
          _$ReplicaDb,
          $TilesTable,
          Tile,
          $$TilesTableFilterComposer,
          $$TilesTableOrderingComposer,
          $$TilesTableAnnotationComposer,
          $$TilesTableCreateCompanionBuilder,
          $$TilesTableUpdateCompanionBuilder,
          (Tile, BaseReferences<_$ReplicaDb, $TilesTable, Tile>),
          Tile,
          PrefetchHooks Function()
        > {
  $$TilesTableTableManager(_$ReplicaDb db, $TilesTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$TilesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$TilesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$TilesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> sha = const Value.absent(),
                Value<int> bytes = const Value.absent(),
                Value<int> lastUsed = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => TilesCompanion(
                sha: sha,
                bytes: bytes,
                lastUsed: lastUsed,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String sha,
                required int bytes,
                required int lastUsed,
                Value<int> rowid = const Value.absent(),
              }) => TilesCompanion.insert(
                sha: sha,
                bytes: bytes,
                lastUsed: lastUsed,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$TilesTable, Tile>(table),
                  BaseReferences<_$ReplicaDb, $TilesTable, Tile>(db, table, e),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$TilesTableProcessedTableManager =
    ProcessedTableManager<
      _$ReplicaDb,
      $TilesTable,
      Tile,
      $$TilesTableFilterComposer,
      $$TilesTableOrderingComposer,
      $$TilesTableAnnotationComposer,
      $$TilesTableCreateCompanionBuilder,
      $$TilesTableUpdateCompanionBuilder,
      (Tile, BaseReferences<_$ReplicaDb, $TilesTable, Tile>),
      Tile,
      PrefetchHooks Function()
    >;
typedef $$KeyValuesTableCreateCompanionBuilder =
    KeyValuesCompanion Function({
      required String key,
      required String value,
      Value<int> rowid,
    });
typedef $$KeyValuesTableUpdateCompanionBuilder =
    KeyValuesCompanion Function({
      Value<String> key,
      Value<String> value,
      Value<int> rowid,
    });

class $$KeyValuesTableFilterComposer
    extends Composer<_$ReplicaDb, $KeyValuesTable> {
  $$KeyValuesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get key => $composableBuilder(
    column: $table.key,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get value => $composableBuilder(
    column: $table.value,
    builder: (column) => ColumnFilters(column),
  );
}

class $$KeyValuesTableOrderingComposer
    extends Composer<_$ReplicaDb, $KeyValuesTable> {
  $$KeyValuesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get key => $composableBuilder(
    column: $table.key,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get value => $composableBuilder(
    column: $table.value,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$KeyValuesTableAnnotationComposer
    extends Composer<_$ReplicaDb, $KeyValuesTable> {
  $$KeyValuesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get key =>
      $composableBuilder(column: $table.key, builder: (column) => column);

  GeneratedColumn<String> get value =>
      $composableBuilder(column: $table.value, builder: (column) => column);
}

class $$KeyValuesTableTableManager
    extends
        RootTableManager<
          _$ReplicaDb,
          $KeyValuesTable,
          KeyValue,
          $$KeyValuesTableFilterComposer,
          $$KeyValuesTableOrderingComposer,
          $$KeyValuesTableAnnotationComposer,
          $$KeyValuesTableCreateCompanionBuilder,
          $$KeyValuesTableUpdateCompanionBuilder,
          (KeyValue, BaseReferences<_$ReplicaDb, $KeyValuesTable, KeyValue>),
          KeyValue,
          PrefetchHooks Function()
        > {
  $$KeyValuesTableTableManager(_$ReplicaDb db, $KeyValuesTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$KeyValuesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$KeyValuesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$KeyValuesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> key = const Value.absent(),
                Value<String> value = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => KeyValuesCompanion(key: key, value: value, rowid: rowid),
          createCompanionCallback:
              ({
                required String key,
                required String value,
                Value<int> rowid = const Value.absent(),
              }) => KeyValuesCompanion.insert(
                key: key,
                value: value,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map(
                (e) => (
                  e.readTable<$KeyValuesTable, KeyValue>(table),
                  BaseReferences<_$ReplicaDb, $KeyValuesTable, KeyValue>(
                    db,
                    table,
                    e,
                  ),
                ),
              )
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$KeyValuesTableProcessedTableManager =
    ProcessedTableManager<
      _$ReplicaDb,
      $KeyValuesTable,
      KeyValue,
      $$KeyValuesTableFilterComposer,
      $$KeyValuesTableOrderingComposer,
      $$KeyValuesTableAnnotationComposer,
      $$KeyValuesTableCreateCompanionBuilder,
      $$KeyValuesTableUpdateCompanionBuilder,
      (KeyValue, BaseReferences<_$ReplicaDb, $KeyValuesTable, KeyValue>),
      KeyValue,
      PrefetchHooks Function()
    >;

class $ReplicaDbManager {
  final _$ReplicaDb _db;
  $ReplicaDbManager(this._db);
  $$ProjectsTableTableManager get projects =>
      $$ProjectsTableTableManager(_db, _db.projects);
  $$OpsTableTableManager get ops => $$OpsTableTableManager(_db, _db.ops);
  $$OutboxEntriesTableTableManager get outboxEntries =>
      $$OutboxEntriesTableTableManager(_db, _db.outboxEntries);
  $$DigestsTableTableManager get digests =>
      $$DigestsTableTableManager(_db, _db.digests);
  $$ManifestsTableTableManager get manifests =>
      $$ManifestsTableTableManager(_db, _db.manifests);
  $$TilesTableTableManager get tiles =>
      $$TilesTableTableManager(_db, _db.tiles);
  $$KeyValuesTableTableManager get keyValues =>
      $$KeyValuesTableTableManager(_db, _db.keyValues);
}
