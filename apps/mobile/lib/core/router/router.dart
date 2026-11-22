import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:modawem_app/core/router/routes.dart';

const List<GoRouteData> publicRoutes = [LoginRoute(), SignupRoute()];

final routerProvider = Provider((ref) {
  final router = GoRouter(
    routes: $appRoutes,
    initialLocation: const HomeRoute().location,
    redirect: (context, state) {
      final isPublic = publicRoutes.any(
        (r) => state.matchedLocation == r.location,
      );

      if (true && !isPublic) {
        return const LoginRoute().location;
      }

      return null;
    },
  );

  return router;
});
