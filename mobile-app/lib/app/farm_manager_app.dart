import 'package:flutter/material.dart';

import '../features/auth/auth_flow.dart';
import '../theme/app_theme.dart';
import 'app_dependencies.dart';

class FarmManagerApp extends StatelessWidget {
  FarmManagerApp({super.key, AppDependencies? dependencies})
      : dependencies = dependencies ?? BackendAppDependencies();

  final AppDependencies dependencies;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Farm Manager',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      home: AuthFlow(dependencies: dependencies),
    );
  }
}
