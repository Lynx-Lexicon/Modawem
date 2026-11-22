part of '../routes.dart';

class HistoryBranch extends StatefulShellBranchData {
  const HistoryBranch();
}

class HistoryRoute extends GoRouteData with $HistoryRoute {
  const HistoryRoute();

  @override
  Widget build(BuildContext context, GoRouterState state) {
    return const HistoryScreen();
  }
}
