import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/business_repository.dart';
import 'package:farm_manager_app/data/repositories/workbench_repository.dart';
import 'package:farm_manager_app/features/business/crop_template_pages.dart';
import 'package:farm_manager_app/features/business/ledger_manual_create_page.dart';
import 'package:farm_manager_app/features/record_flow/record_flow_controller.dart';
import 'package:farm_manager_app/features/workbench/workbench_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  late RecordingAdapter adapter;
  late ApiClient client;

  setUp(() {
    adapter = RecordingAdapter({
      '/smart-fill/parse': smartFillParseResponse,
      'POST /costs': costRecordResponse,
      '/cycles': paginatedCyclesResponse,
      'POST /cycles': cycleResponse,
      '/crops/templates': paginatedCropTemplatesResponse,
      'POST /crops/templates': cropTemplateResponse,
      '/planting/workers/summary': paginatedWorkerSummariesResponse,
      'POST /planting/workers': workerResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    client = ApiClient(dio: dio);
  });

  Future<void> pumpNarrowScreen(WidgetTester tester, Widget child) async {
    tester.view.physicalSize = const Size(393, 852);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(MaterialApp(home: child));
    await tester.pumpAndSettle();
  }

  BusinessRepository businessRepository() => BusinessRepository(client);

  RecordFlowController recordFlowController() => RecordFlowController(
        workbench: WorkbenchRepository(client),
        billing: BillingRepository(client),
      );

  testWidgets('记录页窄屏入口卡片不产生布局异常', (tester) async {
    await pumpNarrowScreen(
      tester,
      WorkbenchScreen(
        businessRepository: businessRepository(),
        recordFlowController: recordFlowController(),
      ),
    );

    expect(find.text('AI帮我填'), findsOneWidget);
    expect(find.text('自己填'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('记账页横幅窄屏文字不产生布局异常', (tester) async {
    await pumpNarrowScreen(
      tester,
      LedgerManualCreatePage(repository: businessRepository()),
    );

    expect(find.text('记账'), findsWidgets);
    expect(find.text('今日'), findsOneWidget);
    expect(find.text('可追溯'), findsOneWidget);
    expect(find.text('按茬口归集'), findsOneWidget);
    expect(find.text('保存记录'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('作物模板页窄屏横幅和卡片不产生布局异常', (tester) async {
    await pumpNarrowScreen(
      tester,
      CropTemplateListPage(repository: businessRepository()),
    );

    expect(find.text('模板库'), findsOneWidget);
    expect(find.text('番茄'), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
