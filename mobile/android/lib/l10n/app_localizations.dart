import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of S
/// returned by `S.of(context)`.
///
/// Applications need to include `S.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: S.localizationsDelegates,
///   supportedLocales: S.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the S.supportedLocales
/// property.
abstract class S {
  S(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static S of(BuildContext context) {
    return Localizations.of<S>(context, S)!;
  }

  static const LocalizationsDelegate<S> delegate = _SDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[Locale('en')];

  /// No description provided for @appName.
  ///
  /// In en, this message translates to:
  /// **'Truebex'**
  String get appName;

  /// No description provided for @badge.
  ///
  /// In en, this message translates to:
  /// **'First Android version'**
  String get badge;

  /// No description provided for @signInTitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in to open your projects'**
  String get signInTitle;

  /// No description provided for @signInText.
  ///
  /// In en, this message translates to:
  /// **'Use the account you use on truebex.com. Your projects stay on this phone for offline use.'**
  String get signInText;

  /// No description provided for @email.
  ///
  /// In en, this message translates to:
  /// **'E-mail'**
  String get email;

  /// No description provided for @password.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get password;

  /// No description provided for @signIn.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get signIn;

  /// No description provided for @signingIn.
  ///
  /// In en, this message translates to:
  /// **'Signing in…'**
  String get signingIn;

  /// No description provided for @continueWithGoogle.
  ///
  /// In en, this message translates to:
  /// **'Continue with Google'**
  String get continueWithGoogle;

  /// No description provided for @createAccount.
  ///
  /// In en, this message translates to:
  /// **'Create an account'**
  String get createAccount;

  /// No description provided for @googleUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Google sign-in is not set up in this build. Sign in with e-mail and password.'**
  String get googleUnavailable;

  /// No description provided for @signInFailed.
  ///
  /// In en, this message translates to:
  /// **'Sign-in failed: {reason}'**
  String signInFailed(String reason);

  /// No description provided for @signInCheck.
  ///
  /// In en, this message translates to:
  /// **'Check the e-mail address and the password.'**
  String get signInCheck;

  /// No description provided for @sessionEnded.
  ///
  /// In en, this message translates to:
  /// **'Your session ended. Sign in again to send your edits.'**
  String get sessionEnded;

  /// No description provided for @projectsTitle.
  ///
  /// In en, this message translates to:
  /// **'Your projects'**
  String get projectsTitle;

  /// No description provided for @projectsIntro.
  ///
  /// In en, this message translates to:
  /// **'Projects you own and projects shared with you. Star a project to keep it ready offline.'**
  String get projectsIntro;

  /// No description provided for @projectsEmpty.
  ///
  /// In en, this message translates to:
  /// **'No projects yet. Save a project to the cloud from the desktop app, or ask someone to share one with you.'**
  String get projectsEmpty;

  /// No description provided for @projectsLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading your projects…'**
  String get projectsLoading;

  /// No description provided for @star.
  ///
  /// In en, this message translates to:
  /// **'Keep offline'**
  String get star;

  /// No description provided for @unstar.
  ///
  /// In en, this message translates to:
  /// **'Stop keeping offline'**
  String get unstar;

  /// No description provided for @syncedAgo.
  ///
  /// In en, this message translates to:
  /// **'Synced {when}'**
  String syncedAgo(String when);

  /// No description provided for @neverSynced.
  ///
  /// In en, this message translates to:
  /// **'Not synced yet'**
  String get neverSynced;

  /// No description provided for @editsWaiting.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, =1{1 edit waiting} other{{count} edits waiting}}'**
  String editsWaiting(int count);

  /// No description provided for @offline.
  ///
  /// In en, this message translates to:
  /// **'Offline — showing the copy on this phone.'**
  String get offline;

  /// No description provided for @justNow.
  ///
  /// In en, this message translates to:
  /// **'just now'**
  String get justNow;

  /// No description provided for @minutesAgo.
  ///
  /// In en, this message translates to:
  /// **'{n} min ago'**
  String minutesAgo(int n);

  /// No description provided for @hoursAgo.
  ///
  /// In en, this message translates to:
  /// **'{n} h ago'**
  String hoursAgo(int n);

  /// No description provided for @daysAgo.
  ///
  /// In en, this message translates to:
  /// **'{n} d ago'**
  String daysAgo(int n);

  /// No description provided for @roleOwner.
  ///
  /// In en, this message translates to:
  /// **'Owner'**
  String get roleOwner;

  /// No description provided for @roleEditor.
  ///
  /// In en, this message translates to:
  /// **'Editor'**
  String get roleEditor;

  /// No description provided for @roleViewer.
  ///
  /// In en, this message translates to:
  /// **'Viewer'**
  String get roleViewer;

  /// No description provided for @back.
  ///
  /// In en, this message translates to:
  /// **'Projects'**
  String get back;

  /// No description provided for @openingProject.
  ///
  /// In en, this message translates to:
  /// **'Opening the project…'**
  String get openingProject;

  /// No description provided for @projectMissing.
  ///
  /// In en, this message translates to:
  /// **'This project is not shared with this account, or it was deleted.'**
  String get projectMissing;

  /// No description provided for @noPanorama.
  ///
  /// In en, this message translates to:
  /// **'No cloud panorama for this project yet. Start one from the desktop app; it shows here as soon as it is rendered.'**
  String get noPanorama;

  /// No description provided for @noManifest.
  ///
  /// In en, this message translates to:
  /// **'The panorama is still rendering. It shows here as soon as the first tiles are ready.'**
  String get noManifest;

  /// No description provided for @updateNeeded.
  ///
  /// In en, this message translates to:
  /// **'Update needed: this panorama needs a newer version of Truebex.'**
  String get updateNeeded;

  /// No description provided for @panoramaAt.
  ///
  /// In en, this message translates to:
  /// **'Panorama at operation {seq}'**
  String panoramaAt(int seq);

  /// No description provided for @facesUpdated.
  ///
  /// In en, this message translates to:
  /// **'{n} faces updated'**
  String facesUpdated(int n);

  /// No description provided for @view.
  ///
  /// In en, this message translates to:
  /// **'View'**
  String get view;

  /// No description provided for @tilt.
  ///
  /// In en, this message translates to:
  /// **'Tilt to look'**
  String get tilt;

  /// No description provided for @tiltOn.
  ///
  /// In en, this message translates to:
  /// **'Tilting'**
  String get tiltOn;

  /// No description provided for @hint.
  ///
  /// In en, this message translates to:
  /// **'Drag to look around. Tap a label to go to that room.'**
  String get hint;

  /// No description provided for @tabRooms.
  ///
  /// In en, this message translates to:
  /// **'Rooms'**
  String get tabRooms;

  /// No description provided for @tabEdit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get tabEdit;

  /// No description provided for @tabHistory.
  ///
  /// In en, this message translates to:
  /// **'History'**
  String get tabHistory;

  /// No description provided for @tabPeople.
  ///
  /// In en, this message translates to:
  /// **'People'**
  String get tabPeople;

  /// No description provided for @roomsAsOf.
  ///
  /// In en, this message translates to:
  /// **'Rooms as of operation {seq}, {when}'**
  String roomsAsOf(int seq, String when);

  /// No description provided for @roomsNone.
  ///
  /// In en, this message translates to:
  /// **'The rooms list arrives with the project\'s next cloud save from the desktop app.'**
  String get roomsNone;

  /// No description provided for @area.
  ///
  /// In en, this message translates to:
  /// **'{area} m²'**
  String area(String area);

  /// No description provided for @theme.
  ///
  /// In en, this message translates to:
  /// **'Theme'**
  String get theme;

  /// No description provided for @noTheme.
  ///
  /// In en, this message translates to:
  /// **'No theme'**
  String get noTheme;

  /// No description provided for @floor.
  ///
  /// In en, this message translates to:
  /// **'Floor'**
  String get floor;

  /// No description provided for @customFinish.
  ///
  /// In en, this message translates to:
  /// **'Custom finish'**
  String get customFinish;

  /// No description provided for @noFinish.
  ///
  /// In en, this message translates to:
  /// **'No finish'**
  String get noFinish;

  /// No description provided for @edit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get edit;

  /// No description provided for @goTo.
  ///
  /// In en, this message translates to:
  /// **'Go to view'**
  String get goTo;

  /// No description provided for @noPrice.
  ///
  /// In en, this message translates to:
  /// **'No price in {region}'**
  String noPrice(String region);

  /// No description provided for @openings.
  ///
  /// In en, this message translates to:
  /// **'Doors and windows'**
  String get openings;

  /// No description provided for @otherRooms.
  ///
  /// In en, this message translates to:
  /// **'Rooms'**
  String get otherRooms;

  /// No description provided for @editPick.
  ///
  /// In en, this message translates to:
  /// **'Pick a room, a product, a door or a window in Rooms to change it here.'**
  String get editPick;

  /// No description provided for @viewerOnly.
  ///
  /// In en, this message translates to:
  /// **'You can view this project. Ask its owner for editor access to make changes.'**
  String get viewerOnly;

  /// No description provided for @roomTheme.
  ///
  /// In en, this message translates to:
  /// **'Room theme'**
  String get roomTheme;

  /// No description provided for @floorFinish.
  ///
  /// In en, this message translates to:
  /// **'Floor finish'**
  String get floorFinish;

  /// No description provided for @wallFinish.
  ///
  /// In en, this message translates to:
  /// **'Wall finish'**
  String get wallFinish;

  /// No description provided for @wall.
  ///
  /// In en, this message translates to:
  /// **'Wall'**
  String get wall;

  /// No description provided for @move.
  ///
  /// In en, this message translates to:
  /// **'Move'**
  String get move;

  /// No description provided for @moveHint.
  ///
  /// In en, this message translates to:
  /// **'Directions follow the way you are looking.'**
  String get moveHint;

  /// No description provided for @step.
  ///
  /// In en, this message translates to:
  /// **'Step'**
  String get step;

  /// No description provided for @left.
  ///
  /// In en, this message translates to:
  /// **'Left'**
  String get left;

  /// No description provided for @right.
  ///
  /// In en, this message translates to:
  /// **'Right'**
  String get right;

  /// No description provided for @away.
  ///
  /// In en, this message translates to:
  /// **'Away'**
  String get away;

  /// No description provided for @closer.
  ///
  /// In en, this message translates to:
  /// **'Closer'**
  String get closer;

  /// No description provided for @slide.
  ///
  /// In en, this message translates to:
  /// **'Slide along its wall'**
  String get slide;

  /// No description provided for @slideLeft.
  ///
  /// In en, this message translates to:
  /// **'Slide −{step} mm'**
  String slideLeft(int step);

  /// No description provided for @slideRight.
  ///
  /// In en, this message translates to:
  /// **'Slide +{step} mm'**
  String slideRight(int step);

  /// No description provided for @mm.
  ///
  /// In en, this message translates to:
  /// **'{n} mm'**
  String mm(int n);

  /// No description provided for @swapFor.
  ///
  /// In en, this message translates to:
  /// **'Swap for'**
  String get swapFor;

  /// No description provided for @swapLoading.
  ///
  /// In en, this message translates to:
  /// **'Finding products of the same kind…'**
  String get swapLoading;

  /// No description provided for @swapNone.
  ///
  /// In en, this message translates to:
  /// **'No other products of this kind in this region yet.'**
  String get swapNone;

  /// No description provided for @swapOffline.
  ///
  /// In en, this message translates to:
  /// **'Products to swap for show when you are online.'**
  String get swapOffline;

  /// No description provided for @opMove.
  ///
  /// In en, this message translates to:
  /// **'Move {name}'**
  String opMove(String name);

  /// No description provided for @opSwap.
  ///
  /// In en, this message translates to:
  /// **'Swap {name}'**
  String opSwap(String name);

  /// No description provided for @pending.
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get pending;

  /// No description provided for @waiting.
  ///
  /// In en, this message translates to:
  /// **'Waiting for connection'**
  String get waiting;

  /// No description provided for @saved.
  ///
  /// In en, this message translates to:
  /// **'Saved'**
  String get saved;

  /// No description provided for @notSaved.
  ///
  /// In en, this message translates to:
  /// **'Not saved: {reason}'**
  String notSaved(String reason);

  /// No description provided for @conflict.
  ///
  /// In en, this message translates to:
  /// **'{name} changed this first — your edit was replaced'**
  String conflict(String name);

  /// No description provided for @conflictSelf.
  ///
  /// In en, this message translates to:
  /// **'You changed this first on another device — your edit was replaced'**
  String get conflictSelf;

  /// No description provided for @someone.
  ///
  /// In en, this message translates to:
  /// **'Someone'**
  String get someone;

  /// No description provided for @dismiss.
  ///
  /// In en, this message translates to:
  /// **'Dismiss'**
  String get dismiss;

  /// No description provided for @historyEmpty.
  ///
  /// In en, this message translates to:
  /// **'No changes yet.'**
  String get historyEmpty;

  /// No description provided for @recentEdits.
  ///
  /// In en, this message translates to:
  /// **'Your edits'**
  String get recentEdits;

  /// No description provided for @historyOp.
  ///
  /// In en, this message translates to:
  /// **'Operation {seq}'**
  String historyOp(int seq);

  /// No description provided for @historyRestore.
  ///
  /// In en, this message translates to:
  /// **'Restored a version'**
  String get historyRestore;

  /// No description provided for @you.
  ///
  /// In en, this message translates to:
  /// **'you'**
  String get you;

  /// No description provided for @hereNow.
  ///
  /// In en, this message translates to:
  /// **'Here now'**
  String get hereNow;

  /// No description provided for @nobodyHere.
  ///
  /// In en, this message translates to:
  /// **'Nobody else has this project open.'**
  String get nobodyHere;

  /// No description provided for @members.
  ///
  /// In en, this message translates to:
  /// **'People on this project'**
  String get members;

  /// No description provided for @clientDesktop.
  ///
  /// In en, this message translates to:
  /// **'Desktop app'**
  String get clientDesktop;

  /// No description provided for @clientWeb.
  ///
  /// In en, this message translates to:
  /// **'Phone or browser'**
  String get clientWeb;

  /// No description provided for @clientAndroid.
  ///
  /// In en, this message translates to:
  /// **'Android app'**
  String get clientAndroid;

  /// No description provided for @clientHeadset.
  ///
  /// In en, this message translates to:
  /// **'Headset'**
  String get clientHeadset;

  /// No description provided for @clientWorker.
  ///
  /// In en, this message translates to:
  /// **'Cloud'**
  String get clientWorker;

  /// No description provided for @floorOak.
  ///
  /// In en, this message translates to:
  /// **'Oak boards'**
  String get floorOak;

  /// No description provided for @floorStone.
  ///
  /// In en, this message translates to:
  /// **'Stone tiles'**
  String get floorStone;

  /// No description provided for @floorConcrete.
  ///
  /// In en, this message translates to:
  /// **'Polished concrete'**
  String get floorConcrete;

  /// No description provided for @floorSand.
  ///
  /// In en, this message translates to:
  /// **'Warm sand'**
  String get floorSand;

  /// No description provided for @wallChalk.
  ///
  /// In en, this message translates to:
  /// **'Chalk white'**
  String get wallChalk;

  /// No description provided for @wallSage.
  ///
  /// In en, this message translates to:
  /// **'Sage green'**
  String get wallSage;

  /// No description provided for @wallLattice.
  ///
  /// In en, this message translates to:
  /// **'Lattice wallpaper'**
  String get wallLattice;

  /// No description provided for @wallBrick.
  ///
  /// In en, this message translates to:
  /// **'Brick'**
  String get wallBrick;

  /// No description provided for @settings.
  ///
  /// In en, this message translates to:
  /// **'Settings'**
  String get settings;

  /// No description provided for @account.
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get account;

  /// No description provided for @storage.
  ///
  /// In en, this message translates to:
  /// **'Storage on this phone'**
  String get storage;

  /// No description provided for @storageUsed.
  ///
  /// In en, this message translates to:
  /// **'Projects {projects} · Panorama tiles {tiles}'**
  String storageUsed(String projects, String tiles);

  /// No description provided for @clearCache.
  ///
  /// In en, this message translates to:
  /// **'Clear panorama tiles'**
  String get clearCache;

  /// No description provided for @cacheCleared.
  ///
  /// In en, this message translates to:
  /// **'Panorama tiles cleared. They download again when you open a project.'**
  String get cacheCleared;

  /// No description provided for @signOut.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get signOut;

  /// No description provided for @signOutText.
  ///
  /// In en, this message translates to:
  /// **'Signing out removes your projects, edits waiting to be sent and panorama tiles from this phone.'**
  String get signOutText;

  /// No description provided for @privacy.
  ///
  /// In en, this message translates to:
  /// **'Privacy policy'**
  String get privacy;

  /// No description provided for @version.
  ///
  /// In en, this message translates to:
  /// **'Version {version}'**
  String version(String version);

  /// No description provided for @notifyChannel.
  ///
  /// In en, this message translates to:
  /// **'Edits'**
  String get notifyChannel;

  /// No description provided for @notifyChannelText.
  ///
  /// In en, this message translates to:
  /// **'When an edit made on this phone was replaced by someone else\'s.'**
  String get notifyChannelText;

  /// No description provided for @notifyTitle.
  ///
  /// In en, this message translates to:
  /// **'Edit replaced'**
  String get notifyTitle;

  /// No description provided for @networkError.
  ///
  /// In en, this message translates to:
  /// **'Can\'t reach the Truebex server. Your edits wait on this phone until you are back online.'**
  String get networkError;

  /// No description provided for @genericError.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong.'**
  String get genericError;
}

class _SDelegate extends LocalizationsDelegate<S> {
  const _SDelegate();

  @override
  Future<S> load(Locale locale) {
    return SynchronousFuture<S>(lookupS(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en'].contains(locale.languageCode);

  @override
  bool shouldReload(_SDelegate old) => false;
}

S lookupS(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return SEn();
  }

  throw FlutterError(
    'S.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
