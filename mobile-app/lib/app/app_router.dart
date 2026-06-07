import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../features/shell/app_shell.dart';

GoRouter createAppRouter() {
  return GoRouter(
    routes: [
      GoRoute(
        path: '/',
        builder: (BuildContext context, GoRouterState state) =>
            const AppShell(),
      ),
    ],
  );
}
