// The finishes the phone offers (agent-interface §5.10 finish objects): the
// same palette and ids as PF9 (src/lib/app.ts FLOOR and WALL), so an edit made
// on the phone and one made in the browser are the same operation.

import 'dart:convert';

class FinishChoice {
  const FinishChoice(this.id, this.finish);
  final String id;
  final Map<String, Object?> finish;
}

const floorFinishes = <FinishChoice>[
  FinishChoice('oak', {'kind': 'pattern3d', 'pattern': 'slat', 'texture': 'oak', 'tile_mm': [180, 1200]}),
  FinishChoice('stone', {'kind': 'pattern3d', 'pattern': 'tile', 'texture': 'stone', 'tile_mm': [600, 600]}),
  FinishChoice('concrete', {'kind': 'paint', 'colour': '#9A9A96', 'roughness': 0.3}),
  FinishChoice('sand', {'kind': 'paint', 'colour': '#C8B79E', 'roughness': 0.6}),
];

const wallFinishes = <FinishChoice>[
  FinishChoice('chalk', {'kind': 'paint', 'colour': '#F2F0EA', 'roughness': 0.8}),
  FinishChoice('sage', {'kind': 'paint', 'colour': '#9CAF88', 'roughness': 0.8}),
  FinishChoice('lattice', {'kind': 'wallpaper', 'texture': 'lattice'}),
  FinishChoice('brick', {'kind': 'pattern3d', 'pattern': 'brick', 'texture': 'brick', 'tile_mm': [215, 65]}),
];

/// The palette entry a finish matches: its id, `custom` for another finish, null for none.
String? finishId(Object? finish, List<FinishChoice> palette) {
  if (finish == null) return null;
  final text = jsonEncode(finish);
  for (final c in palette) {
    if (jsonEncode(c.finish) == text) return c.id;
  }
  return 'custom';
}
