import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import '../ui/style.dart';

/// Storage used, clear cache, sign out, privacy policy.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.services, required this.onSignedOut});

  final Services services;
  final VoidCallback onSignedOut;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  int? _tiles;
  int? _db;
  String? _email;
  String _notice = '';

  @override
  void initState() {
    super.initState();
    _measure();
  }

  Future<void> _measure() async {
    final tiles = await widget.services.tiles.size();
    var db = 0;
    try {
      final dir = await getApplicationSupportDirectory();
      for (final name in ['truebex-replica.sqlite', 'truebex-replica.sqlite-wal']) {
        final f = File(p.join(dir.path, name));
        if (await f.exists()) db += await f.length();
      }
    } catch (_) {
      // The size is only shown.
    }
    final email = await widget.services.session.email();
    if (mounted) {
      setState(() {
        _tiles = tiles;
        _db = db;
        _email = email;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = S.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(s.settings)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          SectionTitle(s.account),
          Text(_email ?? '', style: const TextStyle(fontSize: 16)),
          SectionTitle(s.storage),
          Text(s.storageUsed(formatBytes(_db ?? 0), formatBytes(_tiles ?? 0)), key: const Key('storageUsed')),
          const SizedBox(height: 12),
          OutlinedButton(
            key: const Key('clearCache'),
            onPressed: () async {
              await widget.services.tiles.clear();
              setState(() => _notice = s.cacheCleared);
              await _measure();
            },
            child: Text(s.clearCache),
          ),
          if (_notice.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_notice, style: const TextStyle(color: Brand.secondary))),
          SectionTitle(s.signOut),
          Text(s.signOutText, style: const TextStyle(color: Brand.secondary)),
          const SizedBox(height: 12),
          FilledButton.tonal(
            key: const Key('signOut'),
            onPressed: () async {
              await widget.services.auth.signOut();
              if (!context.mounted) return;
              Navigator.of(context).popUntil((r) => r.isFirst);
              widget.onSignedOut();
            },
            child: Text(s.signOut),
          ),
          const SizedBox(height: 24),
          TextButton(
            onPressed: () => launchUrl(Uri.parse(Config.privacyUrl), mode: LaunchMode.externalApplication),
            child: Text(s.privacy),
          ),
          Text(s.version('1.0.0'), style: const TextStyle(color: Brand.muted, fontSize: 12)),
        ],
      ),
    );
  }
}
