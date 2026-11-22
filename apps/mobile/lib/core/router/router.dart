import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:modawem_app/core/router/routes.dart';

final routerProvider = Provider((ref) {
  final router = GoRouter(
    routes: $appRoutes,
    initialLocation: const HomeRoute().location,
  );

  return router;
});
