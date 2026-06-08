import 'package:farm_manager_app/features/record_flow/record_ai_confirm_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_manual_edit_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_save_success_screen.dart';
import 'package:flutter/material.dart';
import 'package:golden_toolkit/golden_toolkit.dart';

void main() {
  testGoldens('记录创建闭环三页在 390x844 下稳定渲染', (tester) async {
    final builder = DeviceBuilder()
      ..overrideDevicesForAllScenarios(
        devices: [const Device(name: 'mobile-390', size: Size(390, 844))],
      )
      ..addScenario(widget: const RecordAiConfirmScreen(), name: 'ai-confirm')
      ..addScenario(widget: const RecordManualEditScreen(), name: 'manual-edit')
      ..addScenario(
          widget: const RecordSaveSuccessScreen(), name: 'save-success');

    await tester.pumpDeviceBuilder(builder);
    await screenMatchesGolden(tester, 'record_flow_mobile_screens');
  });
}
