class AppConfig {
  static const String environment = String.fromEnvironment(
    'ENV',
    defaultValue: 'dev',
  );

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:3000',
  );

  static bool get isProduction => environment == 'prod';
  static bool get isStaging => environment == 'staging';
  static bool get isDevelopment => environment == 'dev';
}
