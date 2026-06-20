import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import '../features/auth/auth_flow.dart';
import '../shared/app_identity.dart';
import '../theme/app_theme.dart';
import 'app_dependencies.dart';

class FarmManagerApp extends StatelessWidget {
  FarmManagerApp({super.key, AppDependencies? dependencies})
      : dependencies = dependencies ?? BackendAppDependencies();

  final AppDependencies dependencies;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: AppIdentity.displayName,
      debugShowCheckedModeBanner: false,
      locale: const Locale('zh', 'CN'),
      supportedLocales: const [
        Locale('zh', 'CN'),
        Locale('en', 'US'),
      ],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: AppTheme.light(),
      home: AuthFlow(dependencies: dependencies),
    );
  }
}
