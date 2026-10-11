// Background sync through Android WorkManager (PF10 Design: Jobs / workers):
//
//   truebex.sync      periodic, every 15 min (the platform's minimum) with a
//                     network: push the outbox, pull, refresh digests, and on an
//                     unmetered network prefetch the starred projects' tiles
//   truebex.sync.now  one-off, when the network returns: queued whenever an edit
//                     is made, so an edit made offline goes out without the app
//   truebex.prefetch  one-off, unmetered and charging: a starred project's
//                     panorama moved, fetch its new tiles
//
// The system may defer the periodic job on battery saver; the one-off job and
// the sync on app open cover the edits. A rejection becomes a notification.

import 'dart:ui';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:workmanager/workmanager.dart';

import '../l10n/app_localizations.dart';
import '../services.dart';
import 'sync_engine.dart';

const syncTask = 'truebex.sync';
const syncNowTask = 'truebex.sync.now';
const prefetchTask = 'truebex.prefetch';

/// What the app asks of the background jobs (WorkManager on the phone, nothing in tests).
abstract class SyncScheduler {
  Future<void> start();
  Future<void> syncWhenOnline();
  Future<void> prefetchWhenIdle();
  Future<void> stop();
}

class NoScheduler implements SyncScheduler {
  int onlineRequests = 0;
  int prefetchRequests = 0;

  @override
  Future<void> start() async {}

  @override
  Future<void> syncWhenOnline() async => onlineRequests++;

  @override
  Future<void> prefetchWhenIdle() async => prefetchRequests++;

  @override
  Future<void> stop() async {}
}

class WorkScheduler implements SyncScheduler {
  bool _initialised = false;

  Future<void> _init() async {
    if (_initialised) return;
    await Workmanager().initialize(callbackDispatcher);
    _initialised = true;
  }

  @override
  Future<void> start() async {
    await _init();
    await Workmanager().registerPeriodicTask(
      syncTask,
      syncTask,
      frequency: const Duration(minutes: 15),
      constraints: Constraints(networkType: NetworkType.connected),
      existingWorkPolicy: ExistingPeriodicWorkPolicy.keep,
      backoffPolicy: BackoffPolicy.exponential,
      backoffPolicyDelay: const Duration(seconds: 30),
    );
  }

  @override
  Future<void> syncWhenOnline() async {
    await _init();
    await Workmanager().registerOneOffTask(
      syncNowTask,
      syncNowTask,
      constraints: Constraints(networkType: NetworkType.connected),
      existingWorkPolicy: ExistingWorkPolicy.replace,
      backoffPolicy: BackoffPolicy.exponential,
      backoffPolicyDelay: const Duration(seconds: 10),
    );
  }

  @override
  Future<void> prefetchWhenIdle() async {
    await _init();
    await Workmanager().registerOneOffTask(
      prefetchTask,
      prefetchTask,
      constraints: Constraints(networkType: NetworkType.unmetered, requiresCharging: true),
      existingWorkPolicy: ExistingWorkPolicy.keep,
    );
  }

  @override
  Future<void> stop() async {
    await _init();
    await Workmanager().cancelAll();
  }
}

/// The notifications of the background jobs and the app alike.
class LocalNotifier implements Notifier {
  LocalNotifier(this.strings);

  final S strings;
  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  bool _ready = false;

  Future<void> _init() async {
    if (_ready) return;
    await _plugin.initialize(
      // A white silhouette of the mark (scripts/make_android_assets.py), as Android draws status icons.
      settings: const InitializationSettings(android: AndroidInitializationSettings('@drawable/ic_stat_truebex')),
    );
    _ready = true;
  }

  /// Android 13 and later ask once.
  Future<void> askPermission() async {
    await _init();
    await _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()?.requestNotificationsPermission();
  }

  @override
  Future<void> rejected({required String projectName, required String projectId, required String text, required int id}) async {
    await _init();
    await _plugin.show(
      id: id,
      title: '${strings.notifyTitle} · $projectName',
      body: text,
      notificationDetails: NotificationDetails(
        android: AndroidNotificationDetails(
          'edits',
          strings.notifyChannel,
          channelDescription: strings.notifyChannelText,
          importance: Importance.defaultImportance,
          styleInformation: BigTextStyleInformation(text),
        ),
      ),
      payload: projectId,
    );
  }

  Future<void> clear() async {
    await _init();
    await _plugin.cancelAll();
  }
}

/// The unmetered networks (Wi-Fi, Ethernet) where tiles may be prefetched.
Future<bool> onUnmeteredNetwork() async {
  try {
    final kinds = await Connectivity().checkConnectivity();
    return kinds.contains(ConnectivityResult.wifi) || kinds.contains(ConnectivityResult.ethernet);
  } catch (_) {
    return false;
  }
}

@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, input) async {
    WidgetsFlutterBinding.ensureInitialized();
    DartPluginRegistrant.ensureInitialized();
    final services = await Services.open(background: true);
    try {
      final unmetered = await onUnmeteredNetwork();
      final report = await services.engine.syncAll(unmetered: unmetered, prefetch: task == prefetchTask);
      if (report.prefetchWanted && !unmetered) await services.scheduler.prefetchWhenIdle();
      // false asks WorkManager to retry with backoff (offline, the server busy).
      return !report.retry;
    } catch (_) {
      return false;
    } finally {
      await services.close();
    }
  });
}
