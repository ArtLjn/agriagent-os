import 'package:farm_manager_app/features/shell/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:golden_toolkit/golden_toolkit.dart';

import '../support/fake_app_dependencies.dart';

void main() {
  testGoldens('五个核心页面在 375x812 下稳定渲染', (tester) async {
    final dependencies = FakeAppDependencies();
    final builder = DeviceBuilder()
      ..overrideDevicesForAllScenarios(
        devices: [const Device(name: 'iphone-375', size: Size(375, 812))],
      )
      ..addScenario(
        widget: AppShell(dependencies: dependencies),
        name: 'home',
      )
      ..addScenario(
        widget: AppShell(dependencies: dependencies, initialIndex: 1),
        name: 'record',
      )
      ..addScenario(
        widget: AppShell(dependencies: dependencies, initialIndex: 2),
        name: 'yaya',
      )
      ..addScenario(
        widget: AppShell(dependencies: dependencies, initialIndex: 3),
        name: 'ledger',
      )
      ..addScenario(
        widget: AppShell(dependencies: dependencies, initialIndex: 4),
        name: 'profile',
      );

    await tester.pumpDeviceBuilder(builder);
    await screenMatchesGolden(tester, 'farm_manager_mobile_screens');
  });
}
