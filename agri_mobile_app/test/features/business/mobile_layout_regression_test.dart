import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/business_repository.dart';
import 'package:farm_manager_app/features/business/crop_template_pages.dart';
import 'package:farm_manager_app/features/business/farm_log_create_page.dart';
import 'package:farm_manager_app/features/business/ledger_manual_create_page.dart';
import 'package:farm_manager_app/features/business/wage_create_page.dart';
import 'package:farm_manager_app/features/shell/bottom_tab_bar.dart';
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
      'POST /cost-records': costRecordResponse,
      '/cost-categories': {
        'items': [categoryResponse]
      },
      '/crop-cycles': paginatedCyclesResponse,
      'POST /crop-cycles': cycleResponse,
      '/crop-templates': paginatedCropTemplatesResponse,
      'POST /crop-templates': cropTemplateResponse,
      '/workers/summary': paginatedWorkerSummariesResponse,
      'POST /workers': workerResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
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

  testWidgets('记录页窄屏入口卡片不产生布局异常', (tester) async {
    await pumpNarrowScreen(
      tester,
      WorkbenchScreen(
        businessRepository: businessRepository(),
      ),
    );

    expect(find.text('让芽芽帮你整理'), findsOneWidget);
    expect(find.text('手动记一笔'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('记账表单在窄屏可直接填写金额', (tester) async {
    await pumpNarrowScreen(
      tester,
      LedgerManualCreatePage(repository: businessRepository()),
    );

    expect(find.text('记账'), findsWidgets);
    expect(find.text('金额'), findsOneWidget);
    expect(find.text('保存记录'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('记录创建页不叠加主导航 Tab', (tester) async {
    await pumpNarrowScreen(
      tester,
      LedgerManualCreatePage(repository: businessRepository()),
    );
    expect(find.text('保存记录'), findsOneWidget);
    expect(find.byType(AppBottomTabBar), findsNothing);

    await pumpNarrowScreen(
      tester,
      FarmLogCreatePage(repository: businessRepository()),
    );
    expect(find.text('保存农事'), findsOneWidget);
    expect(find.byType(AppBottomTabBar), findsNothing);

    await pumpNarrowScreen(
      tester,
      WageCreatePage(repository: businessRepository()),
    );
    expect(find.text('保存工资'), findsOneWidget);
    expect(find.byType(AppBottomTabBar), findsNothing);
  });

  testWidgets('作物模板页窄屏列表不产生布局异常', (tester) async {
    await pumpNarrowScreen(
      tester,
      CropTemplateListPage(repository: businessRepository()),
    );

    expect(find.textContaining('个模板'), findsOneWidget);
    expect(find.text('番茄'), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
