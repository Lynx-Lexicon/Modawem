part of '../routes.dart';

class InsightsBranch extends StatefulShellBranchData {
  const InsightsBranch();
}

class InsightsRoute extends GoRouteData with $InsightsRoute {
  const InsightsRoute();

  @override
  Widget build(BuildContext context, GoRouterState state) {
    return const InsightsScreen();
  }
}
