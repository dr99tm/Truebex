import 'dart:async';

import 'package:flutter/material.dart';

import '../l10n/app_localizations.dart';
import '../replica/database.dart';
import '../services.dart';
import '../ui/style.dart';
import 'project_screen.dart';
import 'settings_screen.dart';

/// Owned and shared projects, star to keep offline, each with its sync state
/// ("Synced 2 min ago", "3 edits waiting"). Shown from the phone's copy first.
class ProjectsScreen extends StatefulWidget {
  const ProjectsScreen({super.key, required this.services, required this.onSignedOut});

  final Services services;
  final VoidCallback onSignedOut;

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen> {
  List<Project>? _projects;
  Map<String, int> _waiting = {};
  bool _offline = false;
  bool _syncing = false;
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    unawaited(_load());
    _tick = Timer.periodic(const Duration(seconds: 30), (_) => mounted ? setState(() {}) : null);
    unawaited(_sync());
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  /// The phone's copy: shown at once, offline too.
  Future<void> _load() async {
    final rows = await widget.services.replica.projects();
    final waiting = await widget.services.replica.pendingCounts();
    if (!mounted) return;
    setState(() {
      _projects = rows;
      _waiting = waiting;
    });
  }

  Future<void> _sync() async {
    if (_syncing) return;
    setState(() => _syncing = true);
    final report = await widget.services.engine.syncAll();
    if (!mounted) return;
    if (report.signedOut) {
      widget.onSignedOut();
      return;
    }
    setState(() {
      _syncing = false;
      _offline = report.offline;
    });
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final projects = _projects;
    return Scaffold(
      appBar: AppBar(
        title: Text(s.projectsTitle),
        actions: [
          IconButton(
            tooltip: s.settings,
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
              builder: (_) => SettingsScreen(services: widget.services, onSignedOut: widget.onSignedOut),
            )),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _sync,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          children: [
            Text(s.projectsIntro, style: const TextStyle(color: Brand.secondary)),
            if (_offline)
              Container(
                key: const Key('offlineBanner'),
                margin: const EdgeInsets.only(top: 12),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(border: Border.all(color: Brand.warn.withValues(alpha: 0.5)), borderRadius: BorderRadius.circular(8)),
                child: Row(children: [
                  const Icon(Icons.wifi_off, size: 18, color: Brand.warn),
                  const SizedBox(width: 8),
                  Expanded(child: Text(s.offline, style: const TextStyle(color: Brand.warn))),
                ]),
              ),
            const SizedBox(height: 12),
            if (projects == null || (projects.isEmpty && _syncing))
              Padding(padding: const EdgeInsets.all(24), child: Center(child: Text(s.projectsLoading)))
            else if (projects.isEmpty)
              Padding(padding: const EdgeInsets.all(24), child: Text(s.projectsEmpty, textAlign: TextAlign.center))
            else
              for (final p in projects)
                _ProjectTile(project: p, waiting: _waiting[p.projectId] ?? 0, services: widget.services, onSignedOut: widget.onSignedOut, onChanged: _load),
          ],
        ),
      ),
    );
  }
}

class _ProjectTile extends StatelessWidget {
  const _ProjectTile({required this.project, required this.waiting, required this.services, required this.onSignedOut, required this.onChanged});

  final Project project;
  final int waiting;
  final Services services;
  final VoidCallback onSignedOut;
  final Future<void> Function() onChanged;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final state = waiting > 0
        ? s.editsWaiting(waiting)
        : project.syncedAt == null
            ? s.neverSynced
            : s.syncedAgo(timeAgo(s, project.syncedAt));
    return Card(
      key: Key('project-${project.projectId}'),
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        contentPadding: const EdgeInsets.fromLTRB(16, 8, 4, 8),
        title: Text(project.name, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text('${roleLabel(s, project.role)}${project.ownerName != null && project.role != 'owner' ? ' · ${project.ownerName}' : ''}\n$state',
            style: TextStyle(color: waiting > 0 ? Brand.warn : Brand.secondary)),
        isThreeLine: true,
        trailing: IconButton(
          key: Key('star-${project.projectId}'),
          tooltip: project.starred ? s.unstar : s.star,
          icon: Icon(project.starred ? Icons.star : Icons.star_border, color: project.starred ? Brand.warn : Brand.muted),
          onPressed: () async {
            await services.replica.setStarred(project.projectId, !project.starred);
            if (!project.starred) unawaited(services.scheduler.prefetchWhenIdle());
            await onChanged();
          },
        ),
        onTap: () => Navigator.of(context)
            .push(MaterialPageRoute<void>(
              builder: (_) => ProjectScreen(services: services, projectId: project.projectId, onSignedOut: onSignedOut),
            ))
            .then((_) => onChanged()),
      ),
    );
  }
}
