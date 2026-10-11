// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class SEn extends S {
  SEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'Truebex';

  @override
  String get badge => 'First Android version';

  @override
  String get signInTitle => 'Sign in to open your projects';

  @override
  String get signInText =>
      'Use the account you use on truebex.com. Your projects stay on this phone for offline use.';

  @override
  String get email => 'E-mail';

  @override
  String get password => 'Password';

  @override
  String get signIn => 'Sign in';

  @override
  String get signingIn => 'Signing in…';

  @override
  String get continueWithGoogle => 'Continue with Google';

  @override
  String get createAccount => 'Create an account';

  @override
  String get googleUnavailable =>
      'Google sign-in is not set up in this build. Sign in with e-mail and password.';

  @override
  String signInFailed(String reason) {
    return 'Sign-in failed: $reason';
  }

  @override
  String get signInCheck => 'Check the e-mail address and the password.';

  @override
  String get sessionEnded =>
      'Your session ended. Sign in again to send your edits.';

  @override
  String get projectsTitle => 'Your projects';

  @override
  String get projectsIntro =>
      'Projects you own and projects shared with you. Star a project to keep it ready offline.';

  @override
  String get projectsEmpty =>
      'No projects yet. Save a project to the cloud from the desktop app, or ask someone to share one with you.';

  @override
  String get projectsLoading => 'Loading your projects…';

  @override
  String get star => 'Keep offline';

  @override
  String get unstar => 'Stop keeping offline';

  @override
  String syncedAgo(String when) {
    return 'Synced $when';
  }

  @override
  String get neverSynced => 'Not synced yet';

  @override
  String editsWaiting(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count edits waiting',
      one: '1 edit waiting',
    );
    return '$_temp0';
  }

  @override
  String get offline => 'Offline — showing the copy on this phone.';

  @override
  String get justNow => 'just now';

  @override
  String minutesAgo(int n) {
    return '$n min ago';
  }

  @override
  String hoursAgo(int n) {
    return '$n h ago';
  }

  @override
  String daysAgo(int n) {
    return '$n d ago';
  }

  @override
  String get roleOwner => 'Owner';

  @override
  String get roleEditor => 'Editor';

  @override
  String get roleViewer => 'Viewer';

  @override
  String get back => 'Projects';

  @override
  String get openingProject => 'Opening the project…';

  @override
  String get projectMissing =>
      'This project is not shared with this account, or it was deleted.';

  @override
  String get noPanorama =>
      'No cloud panorama for this project yet. Start one from the desktop app; it shows here as soon as it is rendered.';

  @override
  String get noManifest =>
      'The panorama is still rendering. It shows here as soon as the first tiles are ready.';

  @override
  String get updateNeeded =>
      'Update needed: this panorama needs a newer version of Truebex.';

  @override
  String panoramaAt(int seq) {
    return 'Panorama at operation $seq';
  }

  @override
  String facesUpdated(int n) {
    return '$n faces updated';
  }

  @override
  String get view => 'View';

  @override
  String get tilt => 'Tilt to look';

  @override
  String get tiltOn => 'Tilting';

  @override
  String get hint => 'Drag to look around. Tap a label to go to that room.';

  @override
  String get tabRooms => 'Rooms';

  @override
  String get tabEdit => 'Edit';

  @override
  String get tabHistory => 'History';

  @override
  String get tabPeople => 'People';

  @override
  String roomsAsOf(int seq, String when) {
    return 'Rooms as of operation $seq, $when';
  }

  @override
  String get roomsNone =>
      'The rooms list arrives with the project\'s next cloud save from the desktop app.';

  @override
  String area(String area) {
    return '$area m²';
  }

  @override
  String get theme => 'Theme';

  @override
  String get noTheme => 'No theme';

  @override
  String get floor => 'Floor';

  @override
  String get customFinish => 'Custom finish';

  @override
  String get noFinish => 'No finish';

  @override
  String get edit => 'Edit';

  @override
  String get goTo => 'Go to view';

  @override
  String noPrice(String region) {
    return 'No price in $region';
  }

  @override
  String get openings => 'Doors and windows';

  @override
  String get otherRooms => 'Rooms';

  @override
  String get editPick =>
      'Pick a room, a product, a door or a window in Rooms to change it here.';

  @override
  String get viewerOnly =>
      'You can view this project. Ask its owner for editor access to make changes.';

  @override
  String get roomTheme => 'Room theme';

  @override
  String get floorFinish => 'Floor finish';

  @override
  String get wallFinish => 'Wall finish';

  @override
  String get wall => 'Wall';

  @override
  String get move => 'Move';

  @override
  String get moveHint => 'Directions follow the way you are looking.';

  @override
  String get step => 'Step';

  @override
  String get left => 'Left';

  @override
  String get right => 'Right';

  @override
  String get away => 'Away';

  @override
  String get closer => 'Closer';

  @override
  String get slide => 'Slide along its wall';

  @override
  String slideLeft(int step) {
    return 'Slide −$step mm';
  }

  @override
  String slideRight(int step) {
    return 'Slide +$step mm';
  }

  @override
  String mm(int n) {
    return '$n mm';
  }

  @override
  String get swapFor => 'Swap for';

  @override
  String get swapLoading => 'Finding products of the same kind…';

  @override
  String get swapNone => 'No other products of this kind in this region yet.';

  @override
  String get swapOffline => 'Products to swap for show when you are online.';

  @override
  String opMove(String name) {
    return 'Move $name';
  }

  @override
  String opSwap(String name) {
    return 'Swap $name';
  }

  @override
  String get pending => 'Pending';

  @override
  String get waiting => 'Waiting for connection';

  @override
  String get saved => 'Saved';

  @override
  String notSaved(String reason) {
    return 'Not saved: $reason';
  }

  @override
  String conflict(String name) {
    return '$name changed this first — your edit was replaced';
  }

  @override
  String get conflictSelf =>
      'You changed this first on another device — your edit was replaced';

  @override
  String get someone => 'Someone';

  @override
  String get agentAuthor => 'An assistant or script';

  @override
  String get dismiss => 'Dismiss';

  @override
  String get historyEmpty => 'No changes yet.';

  @override
  String get recentEdits => 'Your edits';

  @override
  String historyOp(int seq) {
    return 'Operation $seq';
  }

  @override
  String get historyRestore => 'Restored a version';

  @override
  String get you => 'you';

  @override
  String get hereNow => 'Here now';

  @override
  String get nobodyHere => 'Nobody else has this project open.';

  @override
  String get members => 'People on this project';

  @override
  String get clientDesktop => 'Desktop app';

  @override
  String get clientWeb => 'Phone or browser';

  @override
  String get clientAndroid => 'Android app';

  @override
  String get clientHeadset => 'Headset';

  @override
  String get clientWorker => 'Cloud';

  @override
  String get floorOak => 'Oak boards';

  @override
  String get floorStone => 'Stone tiles';

  @override
  String get floorConcrete => 'Polished concrete';

  @override
  String get floorSand => 'Warm sand';

  @override
  String get wallChalk => 'Chalk white';

  @override
  String get wallSage => 'Sage green';

  @override
  String get wallLattice => 'Lattice wallpaper';

  @override
  String get wallBrick => 'Brick';

  @override
  String get settings => 'Settings';

  @override
  String get account => 'Account';

  @override
  String get storage => 'Storage on this phone';

  @override
  String storageUsed(String projects, String tiles) {
    return 'Projects $projects · Panorama tiles $tiles';
  }

  @override
  String get clearCache => 'Clear panorama tiles';

  @override
  String get cacheCleared =>
      'Panorama tiles cleared. They download again when you open a project.';

  @override
  String get signOut => 'Sign out';

  @override
  String get signOutText =>
      'Signing out removes your projects, edits waiting to be sent and panorama tiles from this phone.';

  @override
  String get privacy => 'Privacy policy';

  @override
  String version(String version) {
    return 'Version $version';
  }

  @override
  String get notifyChannel => 'Edits';

  @override
  String get notifyChannelText =>
      'When an edit made on this phone was replaced by someone else\'s.';

  @override
  String get notifyTitle => 'Edit replaced';

  @override
  String get networkError =>
      'Can\'t reach the Truebex server. Your edits wait on this phone until you are back online.';

  @override
  String get genericError => 'Something went wrong.';
}
