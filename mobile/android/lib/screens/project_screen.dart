import 'dart:async';

import 'package:flutter/material.dart';

import '../actions/actions.dart';
import '../api/api.dart';
import '../l10n/app_localizations.dart';
import '../project/project_controller.dart';
import '../services.dart';
import '../ui/style.dart';
import '../viewer/panorama_view.dart';
import 'panels.dart';

enum ProjectTab { rooms, edit, history, people }

/// The panorama full screen (the shared viewer in a web view) with a bottom
/// sheet: Rooms, Edit, History (operations with authors), People.
class ProjectScreen extends StatefulWidget {
  const ProjectScreen({super.key, required this.services, required this.projectId, required this.onSignedOut, this.controller, this.surface});

  final Services services;
  final String projectId;
  final VoidCallback onSignedOut;

  /// Tests pass their own (no network loops, a stand-in web view).
  final ProjectController? controller;
  final SurfaceFactory? surface;

  @override
  State<ProjectScreen> createState() => _ProjectScreenState();
}

class _ProjectScreenState extends State<ProjectScreen> with WidgetsBindingObserver {
  late final ProjectController c = widget.controller ?? ProjectController(widget.services, widget.projectId);
  ProjectTab _tab = ProjectTab.rooms;
  Selection? _selection;
  bool _tilt = false;
  final _sheet = DraggableScrollableController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    c.addListener(_changed);
    if (widget.controller == null) unawaited(c.start());
  }

  void _changed() {
    if (!mounted) return;
    if (c.status == ProjectStatus.signedOut) {
      widget.onSignedOut();
      Navigator.of(context).popUntil((r) => r.isFirst);
      return;
    }
    setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) => c.setForeground(state == AppLifecycleState.resumed);

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    c.removeListener(_changed);
    if (widget.controller == null) c.dispose();
    _sheet.dispose();
    super.dispose();
  }

  void _openTab(ProjectTab tab) {
    setState(() => _tab = tab);
    if (_sheet.isAttached && _sheet.size < 0.5) {
      _sheet.animateTo(0.62, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    if (c.status == ProjectStatus.loading) return _centered(s.openingProject);
    if (c.status == ProjectStatus.missing) return _centered(s.projectMissing);

    final manifest = c.set?.manifest;
    final views = manifest?.views ?? const <TileView>[];
    final digest = c.digest?.digest;
    final current = views.where((v) => v.view == c.viewId).firstOrNull ?? views.firstOrNull;
    final dv = digest?.view(current?.view);
    final startYaw = dv?.yawDeg ?? 0;
    final readable = manifest == null || manifestReadable(manifest);

    List<num> eye(TileView v) =>
        digest?.view(v.view)?.eyeMm ?? ((v.eyeMm?.length ?? 0) == 3 ? v.eyeMm! : const <num>[0, 0, 0]);
    final hotspots = current == null
        ? const <Hotspot>[]
        : [
            for (final v in views)
              if (v.view != current.view)
                () {
                  final look = bearingTo(eye(current), eye(v));
                  return Hotspot(id: v.view, label: digest?.view(v.view)?.name ?? v.title ?? s.view, yawDeg: look.yawDeg, pitchDeg: look.pitchDeg);
                }(),
          ];

    final role = c.record?.role.toJson() ?? c.project?.role ?? 'viewer';
    final subtitle = [
      roleLabel(s, role),
      if (c.set != null) s.panoramaAt(c.set!.atSeq),
      if (c.updatedFaces > 0) s.facesUpdated(c.updatedFaces),
    ].join(' · ');

    return Scaffold(
      backgroundColor: Brand.page,
      body: Stack(
        children: [
          Positioned.fill(
            child: current != null && manifest != null && readable
                ? PanoramaView(
                    key: const Key('panorama'),
                    server: widget.services.tileServer..remoteBase = manifest.tilesBase,
                    view: current,
                    hotspots: hotspots,
                    startYaw: startYaw,
                    label: dv?.name ?? current.title ?? s.view,
                    tilt: _tilt,
                    surface: widget.surface,
                    onHotspot: c.chooseView,
                    onTurn: c.look,
                  )
                : Center(
                    child: Padding(
                      padding: const EdgeInsets.all(32),
                      child: Text(
                        !readable ? s.updateNeeded : (c.sets.isNotEmpty || c.set != null ? s.noManifest : s.noPanorama),
                        key: const Key('noPanorama'),
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Brand.secondary),
                      ),
                    ),
                  ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    IconButton.filledTonal(
                      tooltip: s.back,
                      icon: const Icon(Icons.chevron_left),
                      onPressed: () => Navigator.of(context).maybePop(),
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(c.project?.name ?? '', overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                        Text(subtitle, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: Brand.secondary)),
                      ]),
                    ),
                    if (current != null)
                      IconButton.filledTonal(
                        tooltip: _tilt ? s.tiltOn : s.tilt,
                        isSelected: _tilt,
                        icon: const Icon(Icons.explore_outlined),
                        onPressed: () => setState(() => _tilt = !_tilt),
                      ),
                    IconButton.filledTonal(
                      key: const Key('starProject'),
                      tooltip: (c.project?.starred ?? false) ? s.unstar : s.star,
                      icon: Icon((c.project?.starred ?? false) ? Icons.star : Icons.star_border),
                      onPressed: c.toggleStar,
                    ),
                  ]),
                  if (views.length > 1)
                    Padding(
                      padding: const EdgeInsets.only(top: 6, left: 4),
                      child: DropdownButton<String>(
                        key: const Key('viewPicker'),
                        value: current?.view,
                        dropdownColor: Brand.ground,
                        underline: const SizedBox.shrink(),
                        items: [
                          for (final v in views)
                            DropdownMenuItem(value: v.view, child: Text(digest?.view(v.view)?.name ?? v.title ?? s.view)),
                        ],
                        onChanged: (id) => id == null ? null : c.chooseView(id),
                      ),
                    ),
                  if (c.offline) _banner(Icons.wifi_off, s.offline, Brand.warn, const Key('offlineBanner')),
                  if (c.error.isNotEmpty) _banner(Icons.info_outline, c.error, Brand.secondary, const Key('errorBanner')),
                ],
              ),
            ),
          ),
          DraggableScrollableSheet(
            controller: _sheet,
            initialChildSize: 0.2,
            minChildSize: 0.12,
            maxChildSize: 0.85,
            snap: true,
            builder: (context, scroll) => Container(
              decoration: const BoxDecoration(
                color: Brand.surface,
                borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
                border: Border(top: BorderSide(color: Brand.border)),
              ),
              child: ListView(
                controller: scroll,
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                children: [
                  Center(child: Container(width: 36, height: 4, decoration: BoxDecoration(color: Brand.border, borderRadius: BorderRadius.circular(2)))),
                  const SizedBox(height: 8),
                  _tabs(s),
                  const SizedBox(height: 12),
                  switch (_tab) {
                    ProjectTab.rooms => RoomsPanel(
                        controller: c,
                        onGoTo: (roomId) {
                          final v = digest?.views.where((d) => d.room == roomId && views.any((m) => m.view == d.id)).firstOrNull;
                          if (v != null) c.chooseView(v.id);
                          if (_sheet.isAttached) _sheet.animateTo(0.2, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
                        },
                        onEdit: (sel) {
                          setState(() => _selection = sel);
                          _openTab(ProjectTab.edit);
                        },
                      ),
                    ProjectTab.edit => EditPanel(controller: c, selection: _selection),
                    ProjectTab.history => HistoryPanel(controller: c),
                    ProjectTab.people => PeoplePanel(controller: c),
                  },
                  if (_tab == ProjectTab.rooms && digest == null) const SizedBox.shrink(),
                  Padding(padding: const EdgeInsets.only(top: 12), child: Text(s.hint, style: const TextStyle(fontSize: 12, color: Brand.muted))),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _tabs(S s) {
    Widget tab(ProjectTab t, String label, {Widget? extra}) => Expanded(
          child: TextButton(
            key: Key('tab-${t.name}'),
            style: TextButton.styleFrom(
              backgroundColor: _tab == t ? Brand.elevated : Colors.transparent,
              foregroundColor: _tab == t ? Brand.text : Brand.secondary,
            ),
            onPressed: () => _openTab(t),
            child: Row(mainAxisSize: MainAxisSize.min, children: [Flexible(child: Text(label, overflow: TextOverflow.ellipsis)), ?extra]),
          ),
        );
    return Row(children: [
      tab(ProjectTab.rooms, s.tabRooms),
      tab(ProjectTab.edit, s.tabEdit, extra: c.pendingCount > 0 ? const Text(' •', style: TextStyle(color: Brand.warn)) : null),
      tab(ProjectTab.history, s.tabHistory),
      tab(ProjectTab.people, s.tabPeople,
          extra: c.others.isNotEmpty ? Text(' ${c.others.length}', style: const TextStyle(color: Brand.accent)) : null),
    ]);
  }

  Widget _banner(IconData icon, String text, Color color, Key key) => Container(
        key: key,
        margin: const EdgeInsets.only(top: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Brand.page.withValues(alpha: 0.85),
          border: Border.all(color: color.withValues(alpha: 0.5)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Flexible(child: Text(text, style: TextStyle(color: color, fontSize: 13))),
        ]),
      );

  Widget _centered(String text) => Scaffold(
        appBar: AppBar(),
        body: Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(text, textAlign: TextAlign.center))),
      );
}
