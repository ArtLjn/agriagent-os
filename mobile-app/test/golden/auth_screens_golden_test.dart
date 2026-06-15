import 'package:farm_manager_app/features/auth/login_screen.dart';
import 'package:farm_manager_app/features/auth/onboarding_setup_screen.dart';
import 'package:farm_manager_app/features/auth/register_screen.dart';
import 'package:flutter/material.dart';
import 'package:golden_toolkit/golden_toolkit.dart';

import '../support/fake_app_dependencies.dart';

void main() {
  testGoldens('认证页面在 390x844 下稳定渲染', (tester) async {
    final dependencies = FakeAppDependencies();
    final builder = DeviceBuilder()
      ..overrideDevicesForAllScenarios(
        devices: [const Device(name: 'mobile-390', size: Size(390, 844))],
      )
      ..addScenario(
        widget: LoginScreen(
          onLogin: ({required phone, required password}) async {},
          onRegister: () {},
        ),
        name: 'login',
      )
      ..addScenario(
        widget: RegisterScreen(
          onRegister: ({
            required phone,
            required password,
            required nickname,
          }) async {},
          onLogin: () {},
        ),
        name: 'register',
      )
      ..addScenario(
        widget: OnboardingSetupScreen(
          onStart: () {},
          onSkip: () {},
          profile: dependencies.profile,
          location: dependencies.location,
        ),
        name: 'setup',
      );

    await tester.pumpDeviceBuilder(builder);
    await screenMatchesGolden(tester, 'auth_mobile_screens');
  });
}
