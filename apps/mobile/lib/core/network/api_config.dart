abstract final class ApiConfig {
  static const String baseUrl = String.fromEnvironment(
    "API_BASE_URL",
    defaultValue: "https://example.com:1234",
  );
  static const Duration connectionTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 30);
  static const Duration sendTimeout = Duration(seconds: 15);
}
