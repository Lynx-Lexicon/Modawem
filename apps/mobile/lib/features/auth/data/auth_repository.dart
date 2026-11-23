import 'package:modawem_app/features/auth/data/auth_user_model.dart';

abstract interface class AuthRepository {
  Future<AuthUserModel> login(String identifier, String password);

  Future<AuthUserModel> signup(
    String firstName,
    String lastName,
    String? email,
    String? phone,
    String? avatarUrl,
  );

  Future<void> logout();

  Future<AuthUserModel> getCurrentUser();
}
