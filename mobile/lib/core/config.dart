/// Build-time configuration.
///
/// The API base URL is supplied with `--dart-define` so a debug build can point
/// at a laptop while a release build points at production:
///
///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
///
/// 10.0.2.2 is how the Android emulator reaches the host machine's localhost.
library;

class AppConfig {
  const AppConfig._();

  static const String appName = 'Kumaran Crackers';
  static const String tagline = 'Celebrate Every Moment with Kumaran Crackers';

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );

  static const Duration requestTimeout = Duration(seconds: 20);

  /// Products fetched per page in the catalogue.
  static const int pageSize = 20;
}
