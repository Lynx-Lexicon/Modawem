import 'package:dio/dio.dart';

class AuthInterceptor extends QueuedInterceptor {
  AuthInterceptor({required this._dio, required this._refreshDio});

  final Dio _dio;
  final Dio _refreshDio;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final bool requiresAuth = options.extra["requiresAuth"] ?? true;

    if (!requiresAuth) {
      return handler.next(options);
    }
  }
}
