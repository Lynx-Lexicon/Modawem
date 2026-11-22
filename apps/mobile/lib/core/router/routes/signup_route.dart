part of '../routes.dart';

@TypedGoRoute<SignupRoute>(path: "/signup", name: "signup")
class SignupRoute extends GoRouteData with $SignupRoute {
  const SignupRoute();

  @override
  Widget build(BuildContext context, GoRouterState state) {
    return const SignupScreen();
  }
}
