// The panorama on screen (PF10 Scope 3): one view of a followed set, full
// screen, through PF9's viewer bundle in a web view. The page loads from the
// app's tile server (tile_server.dart), so its tile requests are answered from
// the phone's cache when offline. Drag (or tilt the phone) to look around, tap
// a label to go to another view; a newer manifest swaps only changed tiles.

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../api/api.dart';
import 'tile_server.dart';

/// A label floating at a bearing and pitch that leads to another view.
class Hotspot {
  const Hotspot({required this.id, required this.label, required this.yawDeg, required this.pitchDeg});
  final String id;
  final String label;
  final double yawDeg;
  final double pitchDeg;

  Map<String, Object?> toJson() => {'id': id, 'label': label, 'yawDeg': yawDeg, 'pitchDeg': pitchDeg};
}

/// Where the page is drawn: the system web view on the phone, a stand-in in tests.
abstract class ViewerSurface {
  Future<void> load(Uri url);
  Future<void> run(String javascript);
  void onMessage(void Function(String message) handler);
  Widget build(BuildContext context);
}

class WebViewSurface implements ViewerSurface {
  WebViewSurface(Uri origin) {
    controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF161616))
      ..addJavaScriptChannel('TruebexHost', onMessageReceived: (m) => _handler?.call(m.message))
      // The page never leaves the app's own server.
      ..setNavigationDelegate(NavigationDelegate(
        onNavigationRequest: (req) =>
            req.url.startsWith(origin.toString()) ? NavigationDecision.navigate : NavigationDecision.prevent,
      ));
  }

  late final WebViewController controller;
  void Function(String message)? _handler;

  @override
  Future<void> load(Uri url) => controller.loadRequest(url);

  @override
  Future<void> run(String javascript) => controller.runJavaScript(javascript);

  @override
  void onMessage(void Function(String message) handler) => _handler = handler;

  @override
  Widget build(BuildContext context) => WebViewWidget(controller: controller);
}

typedef SurfaceFactory = ViewerSurface Function(Uri origin);

class PanoramaView extends StatefulWidget {
  const PanoramaView({
    super.key,
    required this.server,
    required this.view,
    required this.hotspots,
    required this.startYaw,
    required this.label,
    required this.onHotspot,
    required this.onTurn,
    this.tilt = false,
    this.surface,
  });

  final TileServer server;
  final TileView view;
  final List<Hotspot> hotspots;
  final double startYaw;
  final String label;
  final void Function(String viewId) onHotspot;
  final void Function(double yawDeg, double pitchDeg) onTurn;
  final bool tilt;

  /// Tests pass a stand-in; the app uses the system web view.
  final SurfaceFactory? surface;

  @override
  State<PanoramaView> createState() => _PanoramaViewState();
}

class _PanoramaViewState extends State<PanoramaView> {
  late final ViewerSurface _surface;
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _surface = (widget.surface ?? WebViewSurface.new)(widget.server.origin);
    _surface.onMessage(_message);
    _surface.load(widget.server.viewerUrl);
  }

  void _message(String text) {
    Object? msg;
    try {
      msg = jsonDecode(text);
    } on FormatException {
      return;
    }
    if (msg is! Map) return;
    switch (msg['type']) {
      case 'ready':
        _ready = true;
        _show();
        if (widget.tilt) _surface.run('window.truebex.tilt(true)');
      case 'turn':
        final yaw = msg['yaw'];
        final pitch = msg['pitch'];
        if (yaw is num && pitch is num) widget.onTurn(yaw.toDouble(), pitch.toDouble());
      case 'hotspot':
        final id = msg['id'];
        if (id is String) widget.onHotspot(id);
    }
  }

  void _show() {
    if (!_ready) return;
    final view = jsonEncode(widget.view.toJson());
    final spots = jsonEncode([for (final h in widget.hotspots) h.toJson()]);
    _surface.run('window.truebex.show($view, ${jsonEncode(widget.server.localTilesBase)}, $spots, '
        '${widget.startYaw}, ${jsonEncode(widget.label)})');
  }

  @override
  void didUpdateWidget(PanoramaView old) {
    super.didUpdateWidget(old);
    if (old.view != widget.view || jsonEncode(old.view.toJson()) != jsonEncode(widget.view.toJson())) {
      _show();
    } else if (jsonEncode([for (final h in old.hotspots) h.toJson()]) != jsonEncode([for (final h in widget.hotspots) h.toJson()])) {
      if (_ready) _surface.run('window.truebex.hotspots(${jsonEncode([for (final h in widget.hotspots) h.toJson()])})');
    }
    if (old.tilt != widget.tilt && _ready) _surface.run('window.truebex.tilt(${widget.tilt})');
  }

  @override
  Widget build(BuildContext context) => Semantics(label: widget.label, child: _surface.build(context));
}
