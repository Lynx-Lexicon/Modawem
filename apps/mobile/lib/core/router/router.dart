import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:modawem_app/core/router/routes.dart';
import 'package:modawem_app/features/auth/auth_controller.dart';
import 'package:modawem_app/features/auth/data/auth_user_model.dart';

const List<GoRouteData> authForbiddenRoutes = [LoginRoute(), SignupRoute()];
const List<GoRouteData> publicRoutes = [...authForbiddenRoutes];

final routerProvider = Provider((ref) {
  final authListenable = ValueNotifier<AsyncValue<AuthUserModel?>>(
    const AsyncLoading(),
  );

  ref.onDispose(authListenable.dispose);

  ref.listen(authControllerProvider, (t, newValue) {
    authListenable.value = newValue;
  });

  final router = GoRouter(
    routes: $appRoutes,
    initialLocation: const HomeRoute().location,
    refreshListenable: authListenable,
    redirect: (context, state) {
      final isAuthorized = ref.read(authControllerProvider).value != null;
      final isPublic = publicRoutes.any(
        (r) => state.matchedLocation == r.location,
      );
      final isAuthForbidden = authForbiddenRoutes.any(
        (r) => r.location == state.matchedLocation,
      );

      if (!isAuthorized && !isPublic) {
        return const LoginRoute().location;
      }

      if (isAuthorized && isAuthForbidden) {
        return const HomeRoute().location;
      }

      return null;
    },
  );

  return router;
});
