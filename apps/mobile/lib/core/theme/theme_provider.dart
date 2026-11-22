import 'package:material_ui/material_ui.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:modawem_app/core/l10n/localization_provider.dart';
import 'package:modawem_app/core/theme/app_theme.dart';
import 'package:modawem_app/core/theme/theme_mode_provider.dart';

final themeProvider = Provider((ref) {
  final locale = ref.watch(localizationProvider);
  final mode = ref.watch(themeModeProvider);

  final theme = AppTheme.light(locale);

  return switch (mode) {
    ThemeMode.light => theme,

    // TODO: Implement Dark Mode Functionality
    ThemeMode.dark => theme,
    _ => theme,
  };
});
