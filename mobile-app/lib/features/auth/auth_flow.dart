import 'package:flutter/material.dart';

import '../../app/app_dependencies.dart';
import '../shell/app_shell.dart';
import 'login_screen.dart';
import 'onboarding_setup_screen.dart';
import 'register_screen.dart';

enum AuthStep { restoring, login, register, setup, app }

class AuthFlow extends StatefulWidget {
  const AuthFlow({
    super.key,
    required this.dependencies,
    this.initialStep = AuthStep.login,
  });

  final AppDependencies dependencies;
  final AuthStep initialStep;

  @override
  State<AuthFlow> createState() => _AuthFlowState();
}

class _AuthFlowState extends State<AuthFlow> {
  late AuthStep step = widget.initialStep;

  @override
  void initState() {
    super.initState();
    if (step == AuthStep.login) {
      step = AuthStep.restoring;
      _restoreSession();
    }
  }

  Future<void> _restoreSession() async {
    final restored = await widget.dependencies.restoreSession();
    if (!mounted) return;
    if (!restored) {
      setState(() => step = AuthStep.login);
      return;
    }
    await _enterAfterAuth();
  }

  Future<void> _logout() async {
    await widget.dependencies.logout();
    if (!mounted) return;
    setState(() => step = AuthStep.login);
  }

  Future<void> _enterAfterAuth() async {
    final user = await widget.dependencies.profile.getProfile();
    final location = user.farm?.location?.trim() ?? '';
    if (!mounted) return;
    setState(() => step = location.isEmpty ? AuthStep.setup : AuthStep.app);
  }

  @override
  Widget build(BuildContext context) {
    return switch (step) {
      AuthStep.restoring => const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
      AuthStep.login => LoginScreen(
          onLogin: ({
            required String phone,
            required String password,
          }) async {
            await widget.dependencies.login(phone: phone, password: password);
            await _enterAfterAuth();
          },
          onRegister: () => setState(() => step = AuthStep.register),
        ),
      AuthStep.register => RegisterScreen(
          onRegister: ({
            required String phone,
            required String password,
            required String nickname,
          }) async {
            await widget.dependencies.register(
              phone: phone,
              password: password,
              nickname: nickname,
            );
            if (mounted) setState(() => step = AuthStep.setup);
          },
          onLogin: () => setState(() => step = AuthStep.login),
        ),
      AuthStep.setup => OnboardingSetupScreen(
          profile: widget.dependencies.profile,
          location: widget.dependencies.location,
          onStart: () => setState(() => step = AuthStep.app),
          onSkip: () => setState(() => step = AuthStep.app),
        ),
      AuthStep.app => AppShell(
          dependencies: widget.dependencies,
          onLogout: _logout,
        ),
    };
  }
}
