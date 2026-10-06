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
    try {
      final restored = await widget.dependencies.restoreSession();
      if (!mounted) return;
      if (!restored) {
        setState(() => step = AuthStep.login);
        return;
      }
      await _enterAfterAuth(onFailureMessage: '登录已失效，请重新登录');
    } catch (_) {
      if (!mounted) return;
      setState(() => step = AuthStep.login);
      _showMessage('恢复登录失败，请重新登录');
    }
  }

  Future<void> _logout() async {
    await widget.dependencies.logout();
    if (!mounted) return;
    setState(() => step = AuthStep.login);
  }

  Future<void> _enterAfterAuth({String? onFailureMessage}) async {
    try {
      final user = await widget.dependencies.profile.getProfile();
      final location = user.farm?.location?.trim() ?? '';
      if (!mounted) return;
      setState(() => step = location.isEmpty ? AuthStep.setup : AuthStep.app);
    } catch (_) {
      await widget.dependencies.logout();
      if (!mounted) return;
      setState(() => step = AuthStep.login);
      _showMessage(onFailureMessage ?? '登录失败，请稍后重试');
    }
  }

  void _showMessage(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return switch (step) {
      AuthStep.restoring => const Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
      // 保留两页的表单草稿；认证成功后整个账号入口离开组件树并释放密码。
      AuthStep.login || AuthStep.register => PopScope(
          canPop: step != AuthStep.register,
          onPopInvokedWithResult: (didPop, result) {
            if (!didPop && step == AuthStep.register) {
              FocusScope.of(context).unfocus();
              setState(() => step = AuthStep.login);
            }
          },
          child: IndexedStack(
            index: step == AuthStep.login ? 0 : 1,
            children: [
              LoginScreen(
                onLogin: ({
                  required String phone,
                  required String password,
                }) async {
                  await widget.dependencies
                      .login(phone: phone, password: password);
                  await _enterAfterAuth();
                },
                onRegister: () {
                  FocusScope.of(context).unfocus();
                  setState(() => step = AuthStep.register);
                },
              ),
              RegisterScreen(
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
                onLogin: () {
                  FocusScope.of(context).unfocus();
                  setState(() => step = AuthStep.login);
                },
              ),
            ],
          ),
        ),
      AuthStep.setup => OnboardingSetupScreen(
          profile: widget.dependencies.profile,
          location: widget.dependencies.location,
          locations: widget.dependencies.locations,
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
