part of '../routes.dart';

class ProfileBranch extends StatefulShellBranchData {
  const ProfileBranch();
}

class ProfileRoute extends GoRouteData with $ProfileRoute {
  const ProfileRoute();

  @override
  Widget build(BuildContext context, GoRouterState state) {
    return const ProfileScreen();
  }
}
