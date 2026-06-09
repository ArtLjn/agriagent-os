import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/workbench_repository.dart';
import 'package:farm_manager_app/features/record_flow/record_ai_confirm_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_flow_controller.dart';
import 'package:farm_manager_app/features/record_flow/record_manual_edit_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_save_success_screen.dart';
import 'package:farm_manager_app/features/shell/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';
import '../../support/fake_app_dependencies.dart';

void main() {
  Future<void> pumpFlow(WidgetTester tester, Widget child) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(MaterialApp(home: child));
  }

  RecordFlowController controllerFor(RecordingAdapter adapter) {
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final client = ApiClient(dio: dio);
    return RecordFlowController(
      workbench: WorkbenchRepository(client),
      billing: BillingRepository(client),
    );
  }

  const draft = RecordDraft(
    scene: 'ledger.record',
    originalText: '今天买肥料 200',
    fields: {'amount': '200', 'category': '肥料'},
    missingFields: [],
    warnings: [],
  );

  testWidgets('AI 确认页展示后端解析字段并保存到成功页', (tester) async {
    final adapter = RecordingAdapter({'POST /costs': costRecordResponse});
    await pumpFlow(
      tester,
      RecordAiConfirmScreen(controller: controllerFor(adapter), draft: draft),
    );

    expect(find.text('智能确认'), findsOneWidget);
    expect(find.text('ledger.record'), findsOneWidget);
    expect(find.text('用户原话  今天买肥料 200'), findsOneWidget);
    expect(find.text('识别字段'), findsOneWidget);
    expect(find.text('amount'), findsOneWidget);
    expect(find.text('200'), findsWidgets);
    expect(find.textContaining('/smart-fill'), findsNothing);

    await tester.tap(find.text('确认保存').last);
    await tester.pumpAndSettle();

    expect(find.text('记录已保存'), findsOneWidget);
    expect(find.text('已同步到账本'), findsOneWidget);
    expect(adapter.find('POST', '/costs').data, draft.fields);
  });

  testWidgets('缺字段确认页保留在当前页提示补充', (tester) async {
    final adapter = RecordingAdapter({'POST /costs': costRecordResponse});
    await pumpFlow(
      tester,
      RecordAiConfirmScreen(
        controller: controllerFor(adapter),
        draft: const RecordDraft(
          scene: 'ledger.record',
          originalText: '买肥料',
          fields: {},
          missingFields: ['amount'],
          warnings: [],
        ),
      ),
    );

    await tester.tap(find.text('确认保存').last);
    await tester.pump();

    expect(find.text('智能确认'), findsOneWidget);
    expect(find.textContaining('还有字段需要补充：amount'), findsOneWidget);
    expect(find.text('记录已保存'), findsNothing);
  });

  testWidgets('手动校正页补齐字段后可保存', (tester) async {
    final adapter = RecordingAdapter({'POST /costs': costRecordResponse});
    await pumpFlow(
      tester,
      RecordManualEditScreen(
        controller: controllerFor(adapter),
        draft: const RecordDraft(
          scene: 'ledger.record',
          originalText: '买肥料',
          fields: {'category': '肥料'},
          missingFields: ['amount'],
          warnings: [],
        ),
      ),
    );

    expect(find.text('改一下'), findsOneWidget);
    expect(find.text('补全字段后再保存'), findsOneWidget);
    await tester.enterText(find.widgetWithText(TextField, 'amount（必填）'), '200');
    await tester.tap(find.text('保存修改'));
    await tester.pumpAndSettle();

    expect(find.text('记录已保存'), findsOneWidget);
    expect(adapter.find('POST', '/costs').data, {
      'category': '肥料',
      'amount': '200',
    });
  });

  testWidgets('保存成功页展示接口返回摘要和下一步动作', (tester) async {
    await pumpFlow(
      tester,
      const RecordSaveSuccessScreen(
        result: RecordSaveResult(
          label: '已同步到账本',
          json: {'id': 1, 'category': '肥料', 'amount': '200'},
        ),
      ),
    );

    expect(find.text('记录已保存'), findsOneWidget);
    expect(find.text('已同步到账本'), findsOneWidget);
    expect(find.text('保存结果'), findsOneWidget);
    expect(find.text('category'), findsOneWidget);
    expect(find.text('肥料'), findsOneWidget);
    expect(find.text('再记一笔'), findsOneWidget);
    expect(find.text('查看账本'), findsOneWidget);
    expect(find.text('回到首页'), findsOneWidget);
    expect(find.text('完成'), findsOneWidget);
  });

  testWidgets('记录页入口解析后进入确认页并能从成功页切到账本', (tester) async {
    await pumpFlow(
      tester,
      AppShell(dependencies: FakeAppDependencies(), initialIndex: 1),
    );

    await tester.tap(find.text('AI帮我填'));
    await tester.pumpAndSettle();
    expect(find.text('智能确认'), findsOneWidget);
    expect(find.text('首页'), findsNothing);

    await tester.tap(find.text('确认保存').last);
    await tester.pumpAndSettle();
    expect(find.text('记录已保存'), findsOneWidget);

    await tester.tap(find.text('查看账本'));
    await tester.pumpAndSettle();
    expect(find.text('资金概览'), findsOneWidget);
    expect(find.text('账本'), findsWidgets);
  });

  testWidgets('自己填入口不会默认伪造成账本保存', (tester) async {
    await pumpFlow(
      tester,
      AppShell(dependencies: FakeAppDependencies(), initialIndex: 1),
    );

    await tester.tap(find.text('自己填'));
    await tester.pumpAndSettle();
    expect(find.text('改一下'), findsOneWidget);

    await tester.tap(find.text('保存修改'));
    await tester.pumpAndSettle();

    expect(find.text('记录已保存'), findsNothing);
    expect(find.textContaining('暂不支持保存该记录类型：manual.record'), findsOneWidget);
  });
}
