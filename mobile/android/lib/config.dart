// Build-time settings (`flutter build apk --dart-define=…`), never secrets:
//   TRUEBEX_API              the API (default https://api.truebex.com); a debug
//                            build may point at a LAN test server over http
//   GOOGLE_SERVER_CLIENT_ID  the Web client id of the Google Cloud project, used
//                            as Credential Manager's server client id (GD4)

class Config {
  static const api = String.fromEnvironment('TRUEBEX_API', defaultValue: 'https://api.truebex.com');
  static const googleServerClientId = String.fromEnvironment('GOOGLE_SERVER_CLIENT_ID');
  static const privacyUrl = 'https://truebex.com/privacy/';
  static const signUpUrl = 'https://truebex.com/signup/';

  /// The tile cache's budget (Design: Data).
  static const tileBudgetBytes = 500 * 1024 * 1024;

  /// The newest `truebex-tiles` MAJOR this release's viewer reads.
  static const tilesMajor = 1;
}
