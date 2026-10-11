// The project sheet's panels (PF9's ProjectPanels, native): Rooms by storey
// with products, prices, themes and floor finishes; Edit (theme, floor and
// wall finish, nudges of 50 / 250 mm, swap product, slide doors and windows);
// History (the log with authors, the phone's own edits and their fate);
// People (who is here, members).

import 'dart:async';

import 'package:flutter/material.dart';

import '../actions/actions.dart';
import '../actions/finishes.dart';
import '../api/api.dart';
import '../digest/digest.dart';
import '../l10n/app_localizations.dart';
import '../outbox/outbox.dart';
import '../project/project_controller.dart';
import '../replica/replica.dart';
import '../ui/style.dart';

enum SelectionKind { room, product, opening }

class Selection {
  const Selection(this.kind, this.id);
  final SelectionKind kind;
  final String id;
}

Widget _chip(String label, {required VoidCallback? onTap, bool selected = false, Key? key}) => Padding(
      padding: const EdgeInsets.only(right: 8, bottom: 8),
      child: ChoiceChip(key: key, label: Text(label), selected: selected, onSelected: onTap == null ? null : (_) => onTap()),
    );

// --- Rooms -------------------------------------------------------------------------------------

class RoomsPanel extends StatelessWidget {
  const RoomsPanel({super.key, required this.controller, required this.onGoTo, required this.onEdit});

  final ProjectController controller;
  final void Function(String roomId) onGoTo;
  final void Function(Selection selection) onEdit;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final snap = controller.digest;
    if (snap == null) return Text(s.roomsNone, key: const Key('roomsNone'), style: const TextStyle(color: Brand.secondary));
    final d = snap.digest;
    final storeys = [...d.storeys]..sort((a, b) => a.elevationMm.compareTo(b.elevationMm));
    final known = {for (final st in storeys) st.id};
    final groups = [
      for (final st in storeys) (name: st.name, rooms: d.rooms.where((r) => r.storey == st.id).toList()),
      (name: s.otherRooms, rooms: d.rooms.where((r) => r.storey == null || !known.contains(r.storey)).toList()),
    ].where((g) => g.rooms.isNotEmpty);
    final viewRooms = {for (final v in d.views) ?v.room};
    final pending = controller.pendingSubjects;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(s.roomsAsOf(snap.atSeq, timeAgoText(s, snap.createdAt)), style: const TextStyle(fontSize: 12, color: Brand.muted)),
      for (final g in groups) ...[
        SectionTitle(g.name),
        for (final room in g.rooms) _RoomCard(room: room, digest: d, controller: controller, pending: pending, canGo: viewRooms.contains(room.id), onGoTo: onGoTo, onEdit: onEdit),
      ],
    ]);
  }
}

class _RoomCard extends StatelessWidget {
  const _RoomCard({required this.room, required this.digest, required this.controller, required this.pending, required this.canGo, required this.onGoTo, required this.onEdit});

  final DigestRoom room;
  final ProjectDigest digest;
  final ProjectController controller;
  final Set<String> pending;
  final bool canGo;
  final void Function(String roomId) onGoTo;
  final void Function(Selection selection) onEdit;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final products = digest.products.where((p) => p.room == room.id).toList();
    final openings = digest.openings.where((o) => o.room == room.id).toList();
    final facts = [
      if (room.areaM2 != null) s.area(room.areaM2!.toStringAsFixed(1)),
      '${s.theme}: ${digest.themeName(room.theme) ?? s.noTheme}',
      '${s.floor}: ${currentFloor(s, room.floor) ?? s.noFinish}',
    ].join(' · ');
    return Card(
      key: Key('room-${room.id}'),
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Row(children: [
                Flexible(child: Text(room.name, style: const TextStyle(fontWeight: FontWeight.w600))),
                if (pending.contains(room.id)) StateBadge(s.pending),
              ]),
            ),
            if (canGo) TextButton(onPressed: () => onGoTo(room.id), child: Text(s.goTo)),
            OutlinedButton(key: Key('editRoom-${room.id}'), onPressed: () => onEdit(Selection(SelectionKind.room, room.id)), child: Text(s.edit)),
          ]),
          Text(facts, style: const TextStyle(fontSize: 12, color: Brand.secondary)),
          for (final p in products)
            InkWell(
              key: Key('product-${p.id}'),
              onTap: () => onEdit(Selection(SelectionKind.product, p.id)),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(children: [
                  Expanded(child: Row(children: [Flexible(child: Text(p.name)), if (pending.contains(p.id)) StateBadge(s.pending)])),
                  Text(
                    controller.prices[p.priceKey] != null
                        ? formatMoney(controller.prices[p.priceKey]!)
                        : (digest.region != null ? s.noPrice(digest.region!) : ''),
                    style: const TextStyle(fontSize: 12, color: Brand.secondary),
                  ),
                ]),
              ),
            ),
          if (openings.isNotEmpty)
            Wrap(crossAxisAlignment: WrapCrossAlignment.center, children: [
              Text('${s.openings}: ', style: const TextStyle(fontSize: 12, color: Brand.secondary)),
              for (final o in openings)
                TextButton(
                  key: Key('opening-${o.id}'),
                  onPressed: () => onEdit(Selection(SelectionKind.opening, o.id)),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [Text(o.name), if (pending.contains(o.id)) StateBadge(s.pending)]),
                ),
            ]),
        ]),
      ),
    );
  }
}

// --- Edit ---------------------------------------------------------------------------------------

class EditPanel extends StatelessWidget {
  const EditPanel({super.key, required this.controller, required this.selection});

  final ProjectController controller;
  final Selection? selection;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final d = controller.digest?.digest;
    final sel = selection;
    final room = sel?.kind == SelectionKind.room ? d?.room(sel!.id) : null;
    final product = sel?.kind == SelectionKind.product ? d?.product(sel!.id) : null;
    final opening = sel?.kind == SelectionKind.opening ? d?.opening(sel!.id) : null;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (d == null || (room == null && product == null && opening == null))
        Text(s.editPick, style: const TextStyle(color: Brand.secondary))
      else ...[
        if (!controller.canEdit)
          Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(border: Border.all(color: Brand.border), borderRadius: BorderRadius.circular(8)),
            child: Text(s.viewerOnly, style: const TextStyle(color: Brand.secondary)),
          ),
        if (room != null) _RoomEdit(key: ValueKey(room.id), room: room, digest: d, controller: controller),
        if (product != null) _ProductEdit(key: ValueKey(product.id), product: product, region: d.region, controller: controller),
        if (opening != null) _OpeningEdit(key: ValueKey(opening.id), opening: opening, controller: controller),
      ],
      SectionTitle(s.recentEdits),
      _Entries(controller: controller, limit: 5),
    ]);
  }
}

class _RoomEdit extends StatefulWidget {
  const _RoomEdit({super.key, required this.room, required this.digest, required this.controller});
  final DigestRoom room;
  final ProjectDigest digest;
  final ProjectController controller;

  @override
  State<_RoomEdit> createState() => _RoomEditState();
}

class _RoomEditState extends State<_RoomEdit> {
  late String? _wallId = widget.room.walls.firstOrNull?.id;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final room = widget.room;
    final c = widget.controller;
    final can = c.canEdit;
    final wall = room.walls.where((w) => w.id == _wallId).firstOrNull ?? room.walls.firstOrNull;
    final floorNow = finishId(room.floor, floorFinishes);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(room.name, style: Theme.of(context).textTheme.titleLarge),
      SectionTitle(s.roomTheme),
      Wrap(children: [
        for (final t in widget.digest.themes)
          _chip(t.name,
              key: Key('theme-${t.id}'),
              selected: t.id == room.theme,
              onTap: can ? () => c.edit(EditRequest(name: s.roomTheme, label: '${s.roomTheme}: ${t.name}', subject: room.id, call: applyTheme(room.id, t.id))) : null),
      ]),
      SectionTitle(s.floorFinish),
      Wrap(children: [
        for (final f in floorFinishes)
          _chip(finishLabel(s, f.id),
              key: Key('floor-${f.id}'),
              selected: floorNow == f.id,
              onTap: can
                  ? () => c.edit(EditRequest(
                        name: s.floorFinish,
                        label: '${s.floorFinish}: ${finishLabel(s, f.id)} (${room.name})',
                        subject: room.id,
                        call: fillFace(room.id, 'floor', f.finish),
                      ))
                  : null),
      ]),
      if (wall != null) ...[
        SectionTitle(s.wallFinish),
        DropdownButton<String>(
          key: const Key('wallPicker'),
          value: wall.id,
          dropdownColor: Brand.ground,
          items: [for (final w in room.walls) DropdownMenuItem(value: w.id, child: Text(w.name))],
          onChanged: (id) => setState(() => _wallId = id),
        ),
        Wrap(children: [
          for (final f in wallFinishes)
            _chip(finishLabel(s, f.id),
                key: Key('wall-${f.id}'),
                onTap: can
                    ? () => c.edit(EditRequest(
                          name: s.wallFinish,
                          label: '${s.wallFinish}: ${finishLabel(s, f.id)} (${room.name}, ${wall.name})',
                          subject: room.id,
                          call: fillFace(wall.id, wall.face, f.finish),
                        ))
                    : null),
        ]),
      ],
    ]);
  }
}

class _StepPicker extends StatelessWidget {
  const _StepPicker({required this.step, required this.onStep});
  final int step;
  final void Function(int) onStep;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return Row(children: [
      Text('${s.step}  ', style: const TextStyle(color: Brand.secondary)),
      for (final n in const [50, 250]) _chip(s.mm(n), selected: n == step, onTap: () => onStep(n)),
    ]);
  }
}

/// A same-category product the placed one can be swapped for.
class SwapChoice {
  const SwapChoice({required this.name, required this.options, required this.ref, this.price});
  final String name;
  final String options;
  final Map<String, String> ref;
  final Price? price;
}

/// Same-category products (5.3 → 5.4), the placed variant and unavailable ones left out.
Future<List<SwapChoice>> swapChoices(TruebexApi api, DigestProduct product, String? region) async {
  final category = product.category;
  if (category == null) return [];
  final found = await api.search(category: category, region: region);
  final out = <SwapChoice>[];
  for (final hit in found.results) {
    final detail = await api.product(hit.productId, region: region);
    for (final v in detail.variants.take(4)) {
      final ref = {'supplier_id': detail.supplierId, 'sku': detail.sku, 'variant_id': v.variantId};
      final current = ref['supplier_id'] == product.product['supplier_id'] && ref['sku'] == product.product['sku'] && ref['variant_id'] == product.product['variant_id'];
      final state = v.availability?.state;
      if (current || state == 'out_of_stock' || state == 'discontinued') continue;
      out.add(SwapChoice(
        name: detail.name,
        options: v.options is Map ? (v.options as Map).values.join(', ') : '',
        ref: ref,
        price: v.price,
      ));
    }
  }
  return out;
}

class _ProductEdit extends StatefulWidget {
  const _ProductEdit({super.key, required this.product, required this.region, required this.controller});
  final DigestProduct product;
  final String? region;
  final ProjectController controller;

  @override
  State<_ProductEdit> createState() => _ProductEditState();
}

class _ProductEditState extends State<_ProductEdit> {
  int _step = 250;
  List<SwapChoice>? _choices;
  bool _swapFailed = false;

  @override
  void initState() {
    super.initState();
    unawaited(swapChoices(widget.controller.services.api, widget.product, widget.region).then((c) {
      if (mounted) setState(() => _choices = c);
    }, onError: (_) {
      if (mounted) {
        setState(() {
          _choices = const [];
          _swapFailed = true;
        });
      }
    }));
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final c = widget.controller;
    final p = widget.product;
    final can = c.canEdit;
    void nudge(Nudge dir, String label) => c.edit(EditRequest(
          name: s.opMove(p.name),
          label: '${s.move} ${p.name}: $label ${s.mm(_step)}',
          subject: p.id,
          call: moveBy([p.id], nudgeVector(c.yawDeg, dir, _step)),
        ));
    Widget pad(Nudge dir, IconData icon, String label) => Padding(
          padding: const EdgeInsets.all(4),
          child: OutlinedButton.icon(
            key: Key('nudge-${dir.name}'),
            onPressed: can ? () => nudge(dir, label) : null,
            icon: Icon(icon, size: 16),
            label: Text(label),
          ),
        );
    final price = c.prices[p.priceKey];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(p.name, style: Theme.of(context).textTheme.titleLarge),
      if (price != null) Text(formatMoney(price), style: const TextStyle(color: Brand.secondary)),
      SectionTitle(s.move),
      _StepPicker(step: _step, onStep: (n) => setState(() => _step = n)),
      Center(child: pad(Nudge.forward, Icons.arrow_upward, s.away)),
      Row(mainAxisAlignment: MainAxisAlignment.center, children: [pad(Nudge.left, Icons.arrow_back, s.left), pad(Nudge.right, Icons.arrow_forward, s.right)]),
      Center(child: pad(Nudge.back, Icons.arrow_downward, s.closer)),
      Text(s.moveHint, style: const TextStyle(fontSize: 12, color: Brand.muted)),
      SectionTitle(s.swapFor),
      if (_choices == null) Text(s.swapLoading, style: const TextStyle(color: Brand.secondary)),
      if (_choices != null && _choices!.isEmpty) Text(_swapFailed ? s.swapOffline : s.swapNone, style: const TextStyle(color: Brand.secondary)),
      for (final choice in _choices ?? const <SwapChoice>[])
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(choice.name),
          subtitle: choice.options.isEmpty ? null : Text(choice.options),
          trailing: Text(choice.price == null ? '' : formatMoney(choice.price!)),
          enabled: can,
          onTap: () => c.edit(EditRequest(
            name: s.opSwap(p.name),
            label: '${s.swapFor} ${choice.name}${choice.options.isEmpty ? '' : ' (${choice.options})'}',
            subject: p.id,
            call: swapProduct(p.id, choice.ref, room: p.room),
          )),
        ),
    ]);
  }
}

class _OpeningEdit extends StatefulWidget {
  const _OpeningEdit({super.key, required this.opening, required this.controller});
  final DigestOpening opening;
  final ProjectController controller;

  @override
  State<_OpeningEdit> createState() => _OpeningEditState();
}

class _OpeningEditState extends State<_OpeningEdit> {
  int _step = 50;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final o = widget.opening;
    final c = widget.controller;
    void slide(int sign) => c.edit(EditRequest(
          name: s.opMove(o.name),
          label: '${o.name}: ${sign > 0 ? s.slideRight(_step) : s.slideLeft(_step)}',
          subject: o.id,
          call: slideAlong(o.id, sign * _step),
        ));
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(o.name, style: Theme.of(context).textTheme.titleLarge),
      SectionTitle(s.slide),
      _StepPicker(step: _step, onStep: (n) => setState(() => _step = n)),
      Row(children: [
        OutlinedButton(key: const Key('slideLeft'), onPressed: c.canEdit ? () => slide(-1) : null, child: Text(s.slideLeft(_step))),
        const SizedBox(width: 8),
        OutlinedButton(key: const Key('slideRight'), onPressed: c.canEdit ? () => slide(1) : null, child: Text(s.slideRight(_step))),
      ]),
    ]);
  }
}

// --- the phone's edits and the history -----------------------------------------------------------

String entryState(S s, ProjectController c, OutboxEntry e) => switch (e.state) {
      EntryState.pending => c.offline ? s.waiting : s.pending,
      EntryState.accepted => s.saved,
      EntryState.rejected => c.services.engine.conflictLine(e, c.authorNames, c.authorId),
      EntryState.failed => s.notSaved(e.reason ?? ''),
      EntryState.dismissed => '',
    };

class _Entries extends StatelessWidget {
  const _Entries({required this.controller, this.limit = 20});
  final ProjectController controller;
  final int limit;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final shown = controller.entries.where((e) => e.state != EntryState.dismissed).take(limit).toList();
    if (shown.isEmpty) return Text(s.historyEmpty, style: const TextStyle(color: Brand.secondary));
    return Column(children: [for (final e in shown) _EntryTile(controller: controller, entry: e)]);
  }
}

class _EntryTile extends StatelessWidget {
  const _EntryTile({required this.controller, required this.entry});
  final ProjectController controller;
  final OutboxEntry entry;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final bad = entry.state == EntryState.rejected || entry.state == EntryState.failed;
    final color = switch (entry.state) {
      EntryState.pending => Brand.warn,
      EntryState.accepted => Brand.accent,
      _ => Theme.of(context).colorScheme.error,
    };
    return ListTile(
      key: Key('entry-${entry.opId}'),
      contentPadding: EdgeInsets.zero,
      dense: true,
      title: Text(entry.label),
      subtitle: Text(entryState(s, controller, entry), key: Key('entryState-${entry.opId}'), style: TextStyle(color: color)),
      trailing: bad ? TextButton(onPressed: () => controller.dismiss(entry.opId), child: Text(s.dismiss)) : null,
    );
  }
}

class HistoryPanel extends StatelessWidget {
  const HistoryPanel({super.key, required this.controller});
  final ProjectController controller;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final items = controller.history;
    if (items.isEmpty) return Text(s.historyEmpty, style: const TextStyle(color: Brand.secondary));
    String who(HistoryItem h) => h.mine ? s.you : (controller.authorNames[h.author] ?? s.someone);
    return Column(children: [
      for (final h in items)
        if (h.entry != null)
          _EntryTile(controller: controller, entry: h.entry!)
        else
          ListTile(
            key: Key('op-${h.serverSeq}'),
            contentPadding: EdgeInsets.zero,
            dense: true,
            title: Text(h.kind == 'restore' ? s.historyRestore : h.name),
            subtitle: Text('${who(h)} · ${timeAgoText(s, h.at)}', style: const TextStyle(color: Brand.secondary)),
            trailing: Text(s.historyOp(h.serverSeq ?? 0), style: const TextStyle(fontSize: 11, color: Brand.muted)),
          ),
    ]);
  }
}

// --- People -------------------------------------------------------------------------------------

class PeoplePanel extends StatelessWidget {
  const PeoplePanel({super.key, required this.controller});
  final ProjectController controller;

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    final meId = controller.me?['id'];
    final members = controller.record?.members ?? const <Member>[];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionTitle(s.hereNow),
      if (controller.others.isEmpty) Text(s.nobodyHere, style: const TextStyle(color: Brand.secondary)),
      for (final p in controller.others)
        ListTile(
          contentPadding: EdgeInsets.zero,
          dense: true,
          leading: const Icon(Icons.circle, size: 10, color: Brand.accent),
          title: Text(p.name ?? s.someone),
          subtitle: Text(clientLabel(s, p.client)),
        ),
      SectionTitle(s.members),
      for (final m in members.where((m) => m.state.toJson() == 'active'))
        ListTile(
          contentPadding: EdgeInsets.zero,
          dense: true,
          title: Text('${m.name ?? m.email}${m.userId == meId ? ' (${s.you})' : ''}'),
          subtitle: Text(roleLabel(s, m.role)),
        ),
    ]);
  }
}
