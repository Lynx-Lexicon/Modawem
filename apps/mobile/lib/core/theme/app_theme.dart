import 'package:material_ui/material_ui.dart';

import 'package:modawem_app/core/theme/colors/app_tokens.dart';

abstract final class AppTheme {
  static final ThemeData light = _buildTheme(Brightness.light, AppTokens.light);
  static final ThemeData dark = _buildTheme(Brightness.light, AppTokens.light);

  static ThemeData _buildTheme(Brightness brightness, AppTokens tokens) {
    final ThemeData base = ThemeData(
      useMaterial3: true,
      brightness: brightness,
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
