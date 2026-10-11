// The app's look: the brand tokens of the desktop app and the site
// (src/app/globals.css @theme), dark, with Segoe UI's fallback family.

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../actions/finishes.dart';
import '../api/api.dart';
import '../l10n/app_localizations.dart';

class Brand {
  static const page = Color(0xFF161616);
  static const ground = Color(0xFF232323);
  static const surface = Color(0xFF1D1D1D);
  static const elevated = Color(0xFF2A2A2A);
  static const border = Color(0xFF3A3A3A);
  static const text = Color(0xFFEDEDED);
  static const secondary = Color(0xFFB4B4B4);
  static const muted = Color(0xFF8A8A8A);
  static const logo = Color(0xFFCBCBCB);
  static const accent = Color(0xFFA0CEFF);
  static const warn = Color(0xFFE2A75C);
}

ThemeData truebexTheme() {
  final scheme = const ColorScheme.dark(
    primary: Brand.accent,
    onPrimary: Brand.page,
    secondary: Brand.accent,
    surface: Brand.surface,
    onSurface: Brand.text,
    error: Color(0xFFFF8A80),
  );
  return ThemeData(
    colorScheme: scheme,
    scaffoldBackgroundColor: Brand.page,
    fontFamily: 'Open Sans',
    appBarTheme: const AppBarTheme(backgroundColor: Brand.page, foregroundColor: Brand.text, elevation: 0),
    cardTheme: const CardThemeData(color: Brand.surface, margin: EdgeInsets.zero),
    dividerColor: Brand.border,
    chipTheme: const ChipThemeData(backgroundColor: Brand.elevated, side: BorderSide(color: Brand.border)),
    inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder(), filled: true, fillColor: Brand.ground),
    useMaterial3: true,
  );
}

String roleLabel(S s, String role) => switch (role) {
      'owner' => s.roleOwner,
      'editor' => s.roleEditor,
      _ => s.roleViewer,
    };

String clientLabel(S s, String client) => switch (client) {
      'desktop' => s.clientDesktop,
      'web' => s.clientWeb,
      'android' => s.clientAndroid,
      'headset' => s.clientHeadset,
      _ => s.clientWorker,
    };

String finishLabel(S s, String id) => switch (id) {
      'oak' => s.floorOak,
      'stone' => s.floorStone,
      'concrete' => s.floorConcrete,
      'sand' => s.floorSand,
      'chalk' => s.wallChalk,
      'sage' => s.wallSage,
      'lattice' => s.wallLattice,
      'brick' => s.wallBrick,
      'custom' => s.customFinish,
      _ => s.noFinish,
    };

String? currentFloor(S s, Object? finish) {
  final id = finishId(finish, floorFinishes);
  return id == null ? null : finishLabel(s, id);
}

/// "just now", "4 min ago", "3 h ago", "2 d ago".
String timeAgo(S s, DateTime? at, {DateTime? now}) {
  if (at == null) return '';
  final d = (now ?? DateTime.now()).difference(at);
  if (d.inMinutes < 1) return s.justNow;
  if (d.inHours < 1) return s.minutesAgo(d.inMinutes);
  if (d.inDays < 1) return s.hoursAgo(d.inHours);
  return s.daysAgo(d.inDays);
}

String timeAgoText(S s, String? rfc3339, {DateTime? now}) => timeAgo(s, rfc3339 == null ? null : DateTime.tryParse(rfc3339), now: now);

/// Minor units in the price's currency (`amount` / 10^`exponent`).
String formatMoney(Price p) {
  final value = p.amount / _pow10(p.exponent);
  return NumberFormat.simpleCurrency(name: p.currency, decimalDigits: p.exponent).format(value);
}

num _pow10(int e) {
  num v = 1;
  for (var i = 0; i < e; i++) {
    v *= 10;
  }
  return v;
}

String formatBytes(int bytes) {
  if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(0)} KB';
  if (bytes < 1024 * 1024 * 1024) return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(2)} GB';
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 16, bottom: 8),
        child: Text(text.toUpperCase(),
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 0.8, color: Brand.muted)),
      );
}

class StateBadge extends StatelessWidget {
  const StateBadge(this.text, {super.key, this.color = Brand.warn});
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(left: 8),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(border: Border.all(color: color.withValues(alpha: 0.6)), borderRadius: BorderRadius.circular(999)),
        child: Text(text, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w500, color: color)),
      );
}
