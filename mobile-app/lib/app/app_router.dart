import 'package:flutter/widgets.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/auth_flow.dart';
import '../features/business/business_pages.dart';
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
      GoRoute(
        path: LedgerManualCreatePage.routePath,
        builder: (context, state) =>
            LedgerManualCreatePage(repository: resolvedDependencies.business),
      ),
      GoRoute(
        path: FarmCycleListPage.routePath,
        builder: (context, state) =>
            FarmCycleListPage(repository: resolvedDependencies.business),
      ),
      GoRoute(
        path: FarmCycleFormPage.routePath,
        builder: (context, state) =>
            FarmCycleFormPage(repository: resolvedDependencies.business),
      ),
      GoRoute(
        path: CropTemplateListPage.routePath,
        builder: (context, state) =>
            CropTemplateListPage(repository: resolvedDependencies.business),
      ),
      GoRoute(
        path: CropTemplateFormPage.routePath,
        builder: (context, state) =>
            CropTemplateFormPage(repository: resolvedDependencies.business),
      ),
      GoRoute(
        path: WorkerListPage.routePath,
        builder: (context, state) =>
            WorkerListPage(repository: resolvedDependencies.business),
      ),
      GoRoute(
        path: WorkerFormPage.routePath,
        builder: (context, state) =>
            WorkerFormPage(repository: resolvedDependencies.business),
      ),
    ],
  );
}
