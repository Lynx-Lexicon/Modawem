import 'package:material_ui/material_ui.dart';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:modawem_app/core/l10n/app_localizations.dart';
import 'package:modawem_app/core/l10n/app_localizations_extension.dart';
import 'package:modawem_app/core/router/router.dart';
import 'package:modawem_app/core/theme/app_theme.dart';

class ModawemApp extends ConsumerWidget {
  const ModawemApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      //
      // Config
      //
      routerConfig: router,
      onGenerateTitle: (context) => context.l10n.appTitle,

      //
      // Theme
      //
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,

      // TODO: Implement theme switch functionality
      themeMode: ThemeMode.light,

      //
      // Locale
      //
      // TODO: Implement localization functionality
      locale: const Locale("ar"),
      supportedLocales: AppLocalizations.supportedLocales,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        ...GlobalMaterialLocalizations.delegates,
      ],
    );
  }
}

// class MainNavigationScreen extends StatefulWidget {
//   const MainNavigationScreen({super.key});

//   @override
//   State<MainNavigationScreen> createState() => _MainNavigationScreenState();
// }

// class _MainNavigationScreenState extends State<MainNavigationScreen> {
//   int _currentIndex = 0;

//   final List<Widget> _screens = const [
//     Center(child: Text('Today - اليوم', style: TextStyle(fontSize: 20))),
//     Center(
//       child: Text('Medications - الأدوية', style: TextStyle(fontSize: 20)),
//     ),
//     Center(
//       child: Text('Insights - الإحصائيات', style: TextStyle(fontSize: 20)),
//     ),
//     Center(child: Text('History - السجل', style: TextStyle(fontSize: 20))),
//     Center(
//       child: Text('Profile - الملف الشخصي', style: TextStyle(fontSize: 20)),
//     ),
//   ];

//   @override
//   Widget build(BuildContext context) {
//     return Scaffold(
//       appBar: AppBar(
//         backgroundColor: const Color.fromARGB(255, 35, 200, 222),
//         title: Text(context.l10n.appTitle),
//       ),
//       body: _screens[_currentIndex],
//       bottomNavigationBar: NavigationBar(
//         selectedIndex: _currentIndex,
//         onDestinationSelected: (int index) {
//           setState(() {
//             _currentIndex = index;
//           });
//         },
//         destinations: [
//           NavigationDestination(
//             icon: const Icon(Icons.today_outlined),
//             selectedIcon: const Icon(Icons.today),
//             label: context.l10n.navBarHome,
//           ),
//           NavigationDestination(
//             icon: const Icon(Icons.medication_outlined),
//             selectedIcon: const Icon(Icons.medication),
//             label: context.l10n.navBarMedications,
//           ),
//           NavigationDestination(
//             icon: const Icon(Icons.insights_outlined),
//             selectedIcon: const Icon(Icons.insights),
//             label: context.l10n.navBarInsights,
//           ),
//           NavigationDestination(
//             icon: const Icon(Icons.history_outlined),
//             selectedIcon: const Icon(Icons.history),
//             label: context.l10n.navBarHistory,
//           ),
//           NavigationDestination(
//             icon: const Icon(Icons.person_outline),
//             selectedIcon: const Icon(Icons.person),
//             label: context.l10n.navBarProfile,
//           ),
//         ],
//       ),
//     );
//   }
// }
