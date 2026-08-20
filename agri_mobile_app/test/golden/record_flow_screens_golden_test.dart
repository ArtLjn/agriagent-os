import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/workbench_repository.dart';
import 'package:farm_manager_app/features/record_flow/record_ai_confirm_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_flow_controller.dart';
import 'package:farm_manager_app/features/record_flow/record_manual_edit_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_save_success_screen.dart';
import 'package:flutter/material.dart';
import 'package:golden_toolkit/golden_toolkit.dart';

import '../support/api_test_fixtures.dart';

void main() {
  testGoldens('记录创建闭环三页在 390x844 下稳定渲染', (tester) async {
    final adapter = RecordingAdapter({'POST /costs': costRecordResponse});
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final client = ApiClient(dio: dio);
    final controller = RecordFlowController(
      workbench: WorkbenchRepository(client),
      billing: BillingRepository(client),
    );
    const draft = RecordDraft(
      scene: 'ledger.record',
      originalText: '今天买肥料 200',
      fields: {'amount': '200', 'category': '肥料'},
      missingFields: [],
      warnings: [],
    );
    final builder = DeviceBuilder()
      ..overrideDevicesForAllScenarios(
        devices: [const Device(name: 'mobile-390', size: Size(390, 844))],
      )
      ..addScenario(
        widget: RecordAiConfirmScreen(controller: controller, draft: draft),
        name: 'ai-confirm',
      )
      ..addScenario(
        widget: RecordManualEditScreen(controller: controller, draft: draft),
        name: 'manual-edit',
      )
      ..addScenario(
        widget: const RecordSaveSuccessScreen(
          result: RecordSaveResult(
            label: '已同步到账本',
            json: {'id': 1, 'category': '肥料', 'amount': '200'},
          ),
        ),
        name: 'save-success',
      );

    await tester.pumpDeviceBuilder(builder);
    await screenMatchesGolden(tester, 'record_flow_mobile_screens');
  });
}
