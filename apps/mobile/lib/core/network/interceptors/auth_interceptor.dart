import 'package:dio/dio.dart';

class AuthInterceptor extends QueuedInterceptor {
  AuthInterceptor({required this._dio, required this._dioRefresh});

  final Dio _dio;
  final Dio _dioRefresh;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final bool requiresAuth = options.extra["requiresAuth"] ?? true;

    if (!requiresAuth) {
      return handler.next(options);
    }

    final String accessToken = await (() async {
      Future.delayed((const Duration(seconds: 3)));
      return "access12345";
    })();

    options.headers['Authorization'] = 'Bearer $accessToken';

    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    final isUnauthorized = err.response?.statusCode == 401;
    final triedRefresh = err.requestOptions.extra['triedRefresh'] == true;

    if (!isUnauthorized || triedRefresh) {
      return handler.next(err);
    }

    try {
      final String refreshToken = await (() async {
        Future.delayed((const Duration(seconds: 3)));
        return "refresh12345";
      })();

      final refreshResponse = await _dioRefresh.post(
        '/auth/refresh',
        data: {'refreshToken': refreshToken},
      );

      final String newAccessToken = refreshResponse.data["accessToken"];
      final String newRefreshToken = refreshResponse.data["refreshToken"];

      // TODO: Save new tokens and replace old revoked ones

      final retryRequestOptions = err.requestOptions;

      retryRequestOptions.headers['Authorization'] = 'Bearer $newAccessToken';
      retryRequestOptions.extra['triedRefresh'] = true;

      final retryResponse = await _dio.fetch(retryRequestOptions);

      return handler.resolve(retryResponse);
    } catch (_) {
      // TODO: Logout and Abort
    }
  }
}
