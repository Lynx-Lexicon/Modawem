import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:modawem_app/features/auth/data/auth_repository.dart';
import 'package:modawem_app/features/auth/data/auth_user_model.dart';

const nour = AuthUserModel(
  id: "abc123",
  firstName: 'Nourullah',
  lastName: 'Yasser',
  email: 'nourullah@modawem.com',
  role: UserRole.admin,
);

class MockAuthRepository implements AuthRepository {
  @override
  Future<AuthUserModel> login(String identifier, String password) async {
    final authResponse = await (() async {
      Future.delayed((const Duration(seconds: 3)));
      return nour;
    })();

    return authResponse;
  }

  @override
  Future<AuthUserModel> signup(
    String firstName,
    String lastName,
    String? email,
    String? phone,
    String? avatarUrl,
  ) async {
    Future.delayed((const Duration(seconds: 3)));
    return nour;
  }

  @override
  Future<void> logout() async {
    Future.delayed((const Duration(seconds: 3)));
  }

  @override
  Future<AuthUserModel> getCurrentUser() async {
    Future.delayed((const Duration(seconds: 3)));
    return nour;
  }
}

final mockAuthRepositoryProvider = Provider<MockAuthRepository>(
  (ref) => MockAuthRepository(),
);
