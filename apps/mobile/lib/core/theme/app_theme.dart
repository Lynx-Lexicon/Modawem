import 'package:material_ui/material_ui.dart';

import 'package:modawem_app/core/theme/colors/app_tokens.dart';

abstract final class AppTheme {
  static ThemeData get light => _buildTheme(Brightness.light, AppTokens.light);
  static ThemeData get dark => _buildTheme(Brightness.light, AppTokens.light);

  static ThemeData _buildTheme(Brightness brightness, AppTokens tokens) {
    return ThemeData(
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
  }
}
