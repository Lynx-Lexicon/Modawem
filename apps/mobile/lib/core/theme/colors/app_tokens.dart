import 'package:material_ui/material_ui.dart';
import 'package:modawem_app/core/theme/colors/app_colors.dart';
import 'package:theme_tailor_annotation/theme_tailor_annotation.dart';

part 'app_tokens.tailor.dart';

@TailorMixin(themeGetter: ThemeGetter.onBuildContext)
class AppTokens extends ThemeExtension<AppTokens> with _$AppTokensTailorMixin {
  AppTokens({
    required this.surfacePrimary,
    required this.surfacePrimaryStrong,
    required this.surfaceSecondary,
    required this.surfaceWhite,
    required this.surfaceNeutral,
    required this.surfaceDisabled,
    required this.surfaceDanger,
    required this.surfaceBeneficial,
    required this.surfaceBeneficialSubtlest,
    required this.surfaceDangerSubtlest,

    required this.textPrimary,
    required this.textSecondary,
    required this.textAccent,
    required this.textAccentStrong,
    required this.textAccentStronger,
    required this.textAccentSubtle,
    required this.textNeutralStrong,
    required this.textDisabled,
    required this.textError,
    required this.textSuccess,

    required this.buttonHover,
    required this.buttonActive,
  });

  // Surface
  @override
  final Color surfacePrimary;
  @override
  final Color surfacePrimaryStrong;
  @override
  final Color surfaceSecondary;
  @override
  final Color surfaceWhite;
  @override
  final Color surfaceNeutral;
  @override
  final Color surfaceDisabled;
  @override
  final Color surfaceDanger;
  @override
  final Color surfaceBeneficial;
  @override
  final Color surfaceBeneficialSubtlest;
  @override
  final Color surfaceDangerSubtlest;

  // Text
  @override
  final Color textPrimary;
  @override
  final Color textSecondary;
  @override
  final Color textAccent;
  @override
  final Color textAccentStrong;
  @override
  final Color textAccentStronger;
  @override
  final Color textAccentSubtle;
  @override
  final Color textNeutralStrong;
  @override
  final Color textDisabled;
  @override
  final Color textError;
  @override
  final Color textSuccess;

  // Button
  @override
  final Color buttonHover;
  @override
  final Color buttonActive;

  static AppTokens light = AppTokens(
    // Surface
    surfacePrimary: AppPrimitives.gold800,
    surfacePrimaryStrong: AppPrimitives.gold500,
    surfaceWhite: AppPrimitives.gold950,
    surfaceSecondary: AppPrimitives.teal500,
    surfaceNeutral: AppPrimitives.gray900,
    surfaceDisabled: AppPrimitives.gray900,
    surfaceDanger: AppPrimitives.red600,
    surfaceBeneficial: AppPrimitives.green500,
    surfaceBeneficialSubtlest: AppPrimitives.green950,
    surfaceDangerSubtlest: AppPrimitives.red950,

    // Text
    textPrimary: AppPrimitives.blue100,
    textSecondary: AppPrimitives.gray700,
    textAccent: AppPrimitives.gold800,
    textAccentStrong: AppPrimitives.gold700,
    textAccentStronger: AppPrimitives.gold500,
    textAccentSubtle: AppPrimitives.gold700,
    textNeutralStrong: AppPrimitives.gray500,
    textDisabled: AppPrimitives.gray700,
    textError: AppPrimitives.red400,
    textSuccess: AppPrimitives.green400,

    // Button
    buttonHover: AppPrimitives.gold700,
    buttonActive: AppPrimitives.gold500,
  );
}
