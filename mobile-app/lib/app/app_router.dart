import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/auth_flow.dart';
import 'app_dependencies.dart';

GoRouter createAppRouter({AppDependencies? dependencies}) {
  final resolvedDependencies = dependencies ?? BackendAppDependencies();
  return GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (BuildContext context, GoRouterState state) =>
            AuthFlow(dependencies: resolvedDependencies),
      ),
    ],
  );
}
