import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/business_repository.dart';
import 'package:farm_manager_app/data/repositories/workbench_repository.dart';
import 'package:farm_manager_app/features/record_flow/record_flow_controller.dart';
import 'package:farm_manager_app/features/workbench/workbench_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  WorkbenchScreen screen() {
    final adapter = RecordingAdapter({
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
    final client = ApiClient(dio: dio);
    return WorkbenchScreen(
      businessRepository: BusinessRepository(client),
      recordFlowController: RecordFlowController(
        workbench: WorkbenchRepository(client),
        billing: BillingRepository(client),
      ),
    );
  }

  WorkbenchScreen screenWithNavigation({
    VoidCallback? onGoHome,
    VoidCallback? onGoLedger,
    VoidCallback? onGoYaya,
    VoidCallback? onGoProfile,
    VoidCallback? onRecordAgain,
  }) {
    final adapter = RecordingAdapter({
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
    final client = ApiClient(dio: dio);
    return WorkbenchScreen(
      businessRepository: BusinessRepository(client),
      recordFlowController: RecordFlowController(
        workbench: WorkbenchRepository(client),
        billing: BillingRepository(client),
      ),
      onGoHome: onGoHome,
      onGoLedger: onGoLedger,
      onGoYaya: onGoYaya,
      onGoProfile: onGoProfile,
      onRecordAgain: onRecordAgain,
    );
  }

  testWidgets('记录页展示 AI 帮填、手动快捷记录和确认卡', (tester) async {
    await tester.pumpWidget(MaterialApp(home: screen()));

    expect(find.bySemanticsLabel('田掌柜'), findsOneWidget);
    expect(find.text('AI帮我填'), findsOneWidget);
    expect(find.text('自己填'), findsOneWidget);
    expect(find.text('例如：今天买饲料 3680 元'), findsOneWidget);
    expect(find.text('记账'), findsOneWidget);
    expect(find.text('建模板'), findsOneWidget);
    expect(find.text('AI待确认'), findsOneWidget);
    expect(find.text('改一下'), findsOneWidget);
    expect(find.text('保存'), findsOneWidget);
    expect(find.text('XX饲料厂'), findsOneWidget);
  });

  testWidgets('工作台不展示 API 路径', (tester) async {
    await tester.pumpWidget(MaterialApp(home: screen()));
    expect(find.textContaining('/'), findsNothing);
  });

  testWidgets('手动快捷记账入口进入记账页', (tester) async {
    await tester.pumpWidget(MaterialApp(home: screen()));

    await tester.tap(find.text('记账').first);
    await tester.pumpAndSettle();

    expect(find.text('保存记录'), findsOneWidget);
    expect(find.text('关联茬口'), findsOneWidget);
  });

  testWidgets('业务页底部 Tab 可回到主导航', (tester) async {
    var selectedIndex = -1;
    await tester.pumpWidget(
      MaterialApp(
        home: screenWithNavigation(
          onGoLedger: () => selectedIndex = 3,
        ),
      ),
    );

    await tester.tap(find.text('记账').first);
    await tester.pumpAndSettle();
    await tester.tap(find.text('账本').last);
    await tester.pumpAndSettle();

    expect(selectedIndex, 3);
    expect(find.text('保存记录'), findsNothing);
  });
}
