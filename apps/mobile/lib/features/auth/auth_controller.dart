import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:modawem_app/features/auth/data/auth_user_model.dart';

import 'package:modawem_app/features/auth/data/mock_auth_repository.dart';

class AuthController extends AsyncNotifier<AuthUserModel?> {
  @override
  Future<AuthUserModel?> build() async {
    final authRepo = ref.read(mockAuthRepositoryProvider);

    // TODO: Get tokens from store
    final String? accessToken = await (() async {
      Future.delayed((const Duration(seconds: 2)));
      // return "access1234";
      return null;
    })();

    if (accessToken == null) {
      return null;
    }

    final currentUser = await authRepo.getCurrentUser();

    return currentUser;
  }

  void login(String identifier, String passwoed) async {
    state = const AsyncLoading();

    final authRepo = ref.read(mockAuthRepositoryProvider);

    state = await AsyncValue.guard(() => authRepo.login(identifier, passwoed));
  }
}

final authControllerProvider =
    AsyncNotifierProvider<AuthController, AuthUserModel?>(
      () => AuthController(),
    );
