import 'package:material_ui/material_ui.dart';

import 'package:modawem_app/core/theme/colors/app_tokens.dart';

enum ThemeType {
  light,
  // dark
}

abstract final class AppTheme {
  static ThemeData light(Locale locale) =>
      _buildTheme(Brightness.light, AppTokens.light, locale);

  // TODO: Implement Dark Mode Functionality
  // static ThemeData dark() => _buildTheme(Brightness.light, AppTokens.light);

  static ThemeData _buildTheme(
    Brightness brightness,
    AppTokens tokens,
    Locale locale,
  ) {
    final bool isArabic = locale.languageCode == "ar";

    final ThemeData base = ThemeData(
      useMaterial3: true,
      brightness: brightness,
      fontFamily: isArabic ? 'Beiruti' : null,
      colorScheme: ColorScheme.fromSeed(
        brightness: brightness,
        seedColor: tokens.surfacePrimary,
        primary: tokens.surfacePrimary,
        error: tokens.surfaceDanger,
      ),

      extensions: [tokens],
    );

    return base.copyWith(
      appBarTheme: AppBarTheme(
        backgroundColor: tokens.surfaceSecondary,
        titleTextStyle: base.textTheme.titleLarge!.copyWith(
          fontWeight: FontWeight.bold,
          fontSize: 24,
        ),
      ),
    );
  }
}
