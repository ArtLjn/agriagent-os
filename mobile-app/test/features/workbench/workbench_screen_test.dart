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
      '/cost-categories': [categoryResponse],
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

  WorkbenchScreen screenWithAdapter(RecordingAdapter adapter) {
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
    VoidCallback? onLedgerSaved,
  }) {
    final adapter = RecordingAdapter({
      '/smart-fill/parse': smartFillParseResponse,
      'POST /costs': costRecordResponse,
      '/cost-categories': [categoryResponse],
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
      onLedgerSaved: onLedgerSaved,
    );
  }

  Future<void> pumpAtWidth(
    WidgetTester tester,
    Widget child, {
    required double width,
  }) async {
    tester.view.physicalSize = Size(width, 812);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(MaterialApp(home: child));
    await tester.pumpAndSettle();
  }

  testWidgets('记录页展示当前工作台入口且不展示语音和样例确认卡', (tester) async {
    await tester.pumpWidget(MaterialApp(home: screen()));

    expect(find.bySemanticsLabel('田掌柜'), findsOneWidget);
    expect(find.text('AI帮我填'), findsOneWidget);
    expect(find.text('输入一句，自动整理成记录'), findsOneWidget);
    expect(find.text('输入一句话记录，芽芽会帮你整理'), findsOneWidget);
    expect(find.text('立即识别'), findsOneWidget);
    expect(find.text('自己填'), findsOneWidget);
    expect(find.text('开始说话'), findsNothing);
    expect(find.text('例如：今天买饲料 3680 元'), findsNothing);
    expect(find.text('记账'), findsOneWidget);
    expect(find.text('建模板'), findsOneWidget);
    expect(find.text('AI待确认'), findsNothing);
    expect(find.text('改一下'), findsNothing);
    expect(find.text('保存'), findsNothing);
    expect(find.text('XX饲料厂'), findsNothing);
  });

  testWidgets('记录页窄屏输入框使用单行短提示', (tester) async {
    await pumpAtWidth(tester, screen(), width: 320);

    expect(find.text('输入一句，芽芽整理'), findsOneWidget);
    expect(find.text('输入一句话记录，芽芽会帮你整理'), findsNothing);
    final field = tester.widget<TextField>(find.byType(TextField).first);
    expect(field.minLines, 1);
    expect(field.maxLines, 1);
  });

  testWidgets('AI 帮填使用用户输入文本解析而不是固定样例', (tester) async {
    final adapter = RecordingAdapter({
      '/smart-fill/parse': smartFillParseResponse,
      'POST /costs': costRecordResponse,
    });
    await tester.pumpWidget(MaterialApp(home: screenWithAdapter(adapter)));

    await tester.enterText(find.byType(TextField), '今天买种子 120 元');
    await tester.tap(find.text('立即识别'));
    await tester.pumpAndSettle();

    final request = adapter.find('POST', '/smart-fill/parse');
    expect(request.data, containsPair('text', '今天买种子 120 元'));
    expect(request.data, isNot(containsPair('text', '今天买饲料 3680 元')));
  });

  testWidgets('工作台不展示 API 路径', (tester) async {
    await tester.pumpWidget(MaterialApp(home: screen()));
    expect(find.textContaining('/'), findsNothing);
  });

  testWidgets('手动快捷记账入口进入记账页', (tester) async {
    await tester.pumpWidget(MaterialApp(home: screen()));

    await tester.tap(find.text('记账').last);
    await tester.pumpAndSettle();

    expect(find.text('保存记录'), findsOneWidget);
    expect(find.text('金额'), findsOneWidget);
  });

  testWidgets('自己填入口进入手动记账页', (tester) async {
    await tester.pumpWidget(MaterialApp(home: screen()));

    await tester.tap(find.text('自己填'));
    await tester.pumpAndSettle();

    expect(find.text('保存记录'), findsOneWidget);
    expect(find.text('金额'), findsOneWidget);
  });

  testWidgets('记农事入口进入农事记录页', (tester) async {
    await tester.pumpWidget(MaterialApp(home: screen()));

    await tester.tap(find.text('记农事'));
    await tester.pumpAndSettle();

    expect(find.text('记农事'), findsWidgets);
    expect(find.text('作业类型'), findsOneWidget);
    expect(find.text('保存农事'), findsOneWidget);
  });

  testWidgets('记工资入口进入工资记录页', (tester) async {
    await tester.pumpWidget(MaterialApp(home: screen()));

    await tester.tap(find.text('记工资'));
    await tester.pumpAndSettle();

    expect(find.text('记工资'), findsWidgets);
    expect(find.text('工人姓名'), findsOneWidget);
    expect(find.text('保存工资'), findsOneWidget);
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

    await tester.tap(find.text('记账').last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('账本').last);
    await tester.pumpAndSettle();

    expect(selectedIndex, 3);
    expect(find.text('保存记录'), findsNothing);
  });

  testWidgets('手动记账保存成功后通知账本刷新', (tester) async {
    var saveNotifications = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: screenWithNavigation(
          onLedgerSaved: () => saveNotifications += 1,
        ),
      ),
    );

    await tester.tap(find.text('记账').last);
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, '输入金额'), '200');
    await tester.tap(find.text('保存记录'));
    await tester.pumpAndSettle();

    expect(find.text('保存记录成功'), findsOneWidget);
    expect(saveNotifications, 1);
  });
}
