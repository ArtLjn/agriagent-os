import 'package:flutter/material.dart';

import '../features/auth/auth_flow.dart';
import '../theme/app_theme.dart';

class FarmManagerApp extends StatelessWidget {
  const FarmManagerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Farm Manager',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      home: const AuthFlow(),
    );
  }
}
