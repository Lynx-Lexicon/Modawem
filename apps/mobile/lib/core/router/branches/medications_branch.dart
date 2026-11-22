part of '../routes.dart';

class MedicationsBranch extends StatefulShellBranchData {
  const MedicationsBranch();
}

class MedicationsRoute extends GoRouteData with $MedicationsRoute {
  const MedicationsRoute();

  @override
  Widget build(BuildContext context, GoRouterState state) {
    return const MedicationsScreen();
  }
}
