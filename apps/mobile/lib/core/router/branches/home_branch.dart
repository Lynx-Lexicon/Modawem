part of '../routes.dart';

class HomeBranch extends StatefulShellBranchData {
  const HomeBranch();
}

class HomeRoute extends GoRouteData with $HomeRoute {
  const HomeRoute();

  @override
  Widget build(BuildContext context, GoRouterState state) {
    return const HomeScreen();
  }
}
