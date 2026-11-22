import 'package:material_ui/material_ui.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:modawem_app/core/l10n/app_localizations.dart';
import 'package:modawem_app/core/l10n/app_localizations_extension.dart';
import 'package:modawem_app/core/l10n/localization_provider.dart';
import 'package:modawem_app/core/router/router.dart';
import 'package:modawem_app/core/theme/theme_provider.dart';

class ModawemApp extends ConsumerWidget {
  const ModawemApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    final locale = ref.watch(localizationProvider);
    final theme = ref.watch(themeProvider);

    return MaterialApp.router(
      //
      // Config
      //
      routerConfig: router,
      onGenerateTitle: (context) => context.l10n.appTitle,

      //
      // Theme
      //
      theme: theme,

      // TODO: Implement theme switch functionality
      // darkTheme: AppTheme.dark,
      themeMode: ThemeMode.light,

      //
      // Locale
      //
      // TODO: Implement localization functionality
      locale: locale,
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        ...GlobalMaterialLocalizations.delegates,
      ],
    );
  }
}
