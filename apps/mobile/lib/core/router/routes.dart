import 'package:material_ui/material_ui.dart';

import 'package:go_router/go_router.dart';

import 'package:modawem_app/features/auth/login_screen.dart';
import 'package:modawem_app/features/auth/signup_screen.dart';
import 'package:modawem_app/features/history/history_screen.dart';
import 'package:modawem_app/features/home/home_screen.dart';
import 'package:modawem_app/features/insights/insights_screen.dart';
import 'package:modawem_app/features/medications/medications_screen.dart';
import 'package:modawem_app/features/profile/profile_screen.dart';
import 'package:modawem_app/shared/shells/app_navbar_shell.dart';

part 'routes.g.dart';

part 'routes/login_route.dart';
part 'routes/signup_route.dart';

part 'branches/home_branch.dart';
part 'branches/medications_branch.dart';
part 'branches/insights_branch.dart';
part 'branches/history_branch.dart';
part 'branches/profile_branch.dart';

@TypedStatefulShellRoute<AppNavBarShellRoute>(
  branches: [
    //
    // Home
    //
    TypedStatefulShellBranch<HomeBranch>(
      routes: [TypedGoRoute<HomeRoute>(path: "/", name: "home")],
    ),

    //
    // Medications
    //
    TypedStatefulShellBranch<MedicationsBranch>(
      routes: [
        TypedGoRoute<MedicationsRoute>(
          path: "/medications",
          name: "medications",
        ),
      ],
    ),

    //
    // Insights
    //
    TypedStatefulShellBranch<InsightsBranch>(
      routes: [
        TypedGoRoute<InsightsRoute>(path: "/insights", name: "insights"),
      ],
    ),

    //
    // History
    //
    TypedStatefulShellBranch<HistoryBranch>(
      routes: [TypedGoRoute<HistoryRoute>(path: "/history", name: "history")],
    ),

    //
    // Profile
    //
    TypedStatefulShellBranch<ProfileBranch>(
      routes: [TypedGoRoute<ProfileRoute>(path: "/profile", name: "profile")],
    ),
  ],
)
class AppNavBarShellRoute extends StatefulShellRouteData {
  const AppNavBarShellRoute();

  @override
  Widget builder(
    BuildContext context,
    GoRouterState state,
    StatefulNavigationShell navigationShell,
  ) {
    return AppNavBarShell(navigationShell);
  }
}
