import 'package:flutter/material.dart';

import '../shell/app_shell.dart';
import 'login_screen.dart';
import 'onboarding_setup_screen.dart';
import 'register_screen.dart';

enum AuthStep { login, register, setup, app }

class AuthFlow extends StatefulWidget {
  const AuthFlow({super.key, this.initialStep = AuthStep.login});

  final AuthStep initialStep;

  @override
  State<AuthFlow> createState() => _AuthFlowState();
}

class _AuthFlowState extends State<AuthFlow> {
  late AuthStep step = widget.initialStep;

  @override
  Widget build(BuildContext context) {
    return switch (step) {
      AuthStep.login => LoginScreen(
          onLogin: () => setState(() => step = AuthStep.app),
          onRegister: () => setState(() => step = AuthStep.register),
        ),
      AuthStep.register => RegisterScreen(
          onRegister: () => setState(() => step = AuthStep.setup),
          onLogin: () => setState(() => step = AuthStep.login),
        ),
      AuthStep.setup => OnboardingSetupScreen(
          onStart: () => setState(() => step = AuthStep.app),
          onSkip: () => setState(() => step = AuthStep.app),
        ),
      AuthStep.app => const AppShell(),
    };
  }
}
