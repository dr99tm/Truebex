// Truebex for Android (PF10): the same light client as the mobile web app
// (PF9), native and built to work without a network — the project log kept on
// the phone, the last panoramas cached, edits made offline and synced in the
// background.

import 'package:flutter/material.dart';

import 'app.dart';
import 'services.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final services = await Services.open();
  await services.tileServer.start();
  runApp(TruebexApp(services: services));
}
