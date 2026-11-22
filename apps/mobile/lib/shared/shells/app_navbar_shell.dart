import 'package:material_ui/material_ui.dart';

import 'package:go_router/go_router.dart';

import 'package:modawem_app/core/l10n/app_localizations_extension.dart';
import 'package:modawem_app/core/router/routes.dart';
import 'package:modawem_app/shared/widgets/app_nav_bar.dart';

class AppNavBarShell extends StatelessWidget {
  const AppNavBarShell(this.navigationShell, {super.key});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    final destinationByLocation = {
      const HomeRoute().location: AppNavDestinationData(
        icon: Icons.today_outlined,
        activeIcon: Icons.today,
        label: context.l10n.navBarHome,
      ),

      const MedicationsRoute().location: AppNavDestinationData(
        icon: Icons.medication_outlined,
        activeIcon: Icons.medication,
        label: context.l10n.navBarMedications,
      ),

      const InsightsRoute().location: AppNavDestinationData(
        icon: Icons.insights_outlined,
        activeIcon: Icons.insights,
        label: context.l10n.navBarInsights,
      ),

      const HistoryRoute().location: AppNavDestinationData(
        icon: Icons.history_outlined,
        activeIcon: Icons.history,
        label: context.l10n.navBarHistory,
      ),

      const ProfileRoute().location: AppNavDestinationData(
        icon: Icons.person_outline,
        activeIcon: Icons.person,
        label: context.l10n.navBarProfile,
      ),
    };

    return Scaffold(
      bottomNavigationBar: AppNavBar(
        selectedDestination: navigationShell.currentIndex,
        onSelectDestination: (index) {
          navigationShell.goBranch(
            index,
            initialLocation: index == navigationShell.currentIndex,
          );
        },
        destinations: navigationShell.route.branches.map((branch) {
          final path =
              branch.initialLocation ?? (branch.routes.first as GoRoute).path;

          final destinationData = destinationByLocation[path];

          if (destinationData == null) {
            throw StateError(
              "No AppNavDestinationData Configured for `$path`!",
            );
          }

          return destinationData;
        }).toList(),
      ),

      body: navigationShell,
    );
  }
}
