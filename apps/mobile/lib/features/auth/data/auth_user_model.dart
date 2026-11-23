import 'package:freezed_annotation/freezed_annotation.dart';

part 'auth_user_model.freezed.dart';
part 'auth_user_model.g.dart';

enum UserRole { patient, prescriber, admin, caregiver, unknown }

@freezed
abstract class AuthUserModel with _$AuthUserModel {
  const factory AuthUserModel({
    required String id,
    required String firstName,
    required String lastName,
    required UserRole role,
    @Default('') String email,
    @Default('') String phone,
    @JsonKey(name: "avatar_url") @Default('') String avatarUrl,
    @JsonKey(name: "is_verified") @Default(false) bool isVerified,
  }) = _AuthUserModel;

  factory AuthUserModel.fromJson(Map<String, dynamic> json) =>
      _$AuthUserModelFromJson(json);
}
