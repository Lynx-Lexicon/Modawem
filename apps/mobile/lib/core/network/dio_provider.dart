import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:modawem_app/core/network/api_config.dart';
import 'package:modawem_app/core/network/interceptors/auth_interceptor.dart';

final baseDioConfig = BaseOptions(
  baseUrl: ApiConfig.baseUrl,
  connectTimeout: ApiConfig.connectionTimeout,
  receiveTimeout: ApiConfig.receiveTimeout,
  sendTimeout: ApiConfig.sendTimeout,
  headers: {"Accept": "application/json", "Content-Type": "application/json"},
  responseType: ResponseType.json,
);

final dioProvider = Provider((ref) {
  final dio = Dio(baseDioConfig);
  final refreshDio = Dio(baseDioConfig);

  dio.interceptors.addAll([AuthInterceptor(dio: dio, dioRefresh: refreshDio)]);

  return dio;
});
