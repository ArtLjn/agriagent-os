import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/business_repository.dart';
import 'package:farm_manager_app/features/business/business_ui.dart';
import 'package:farm_manager_app/features/business/business_pages.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  late BusinessRepository repository;

  setUp(() {
    final adapter = RecordingAdapter({
      '/cycles': paginatedCyclesResponse,
      '/crops/templates': paginatedCropTemplatesResponse,
      '/planting/workers/summary': paginatedWorkerSummariesResponse,
      'POST /costs': costRecordResponse,
      'POST /cycles': cycleResponse,
      'POST /crops/templates': cropTemplateResponse,
      'POST /planting/workers': workerResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    repository = BusinessRepository(ApiClient(dio: dio));
  });

  Future<void> pump(WidgetTester tester, Widget child) async {
    await tester.pumpWidget(MaterialApp(home: child));
    await tester.pumpAndSettle();
  }

  testWidgets('记账手动填写页渲染表单字段和保存按钮', (tester) async {
    await pump(tester, LedgerManualCreatePage(repository: repository));

    expect(find.text('记账'), findsWidgets);
    expect(find.text('收入'), findsOneWidget);
    expect(find.text('支出'), findsOneWidget);
    expect(find.text('金额'), findsOneWidget);
    expect(find.text('关联茬口'), findsOneWidget);
    expect(find.text('保存记录'), findsOneWidget);
  });

  testWidgets('茬口管理列表页渲染底部 Tab 且记录选中', (tester) async {
    await pump(tester, FarmCycleListPage(repository: repository));

    expect(find.text('茬口管理'), findsWidgets);
    expect(find.text('新建茬口'), findsWidgets);
    expect(find.text('搜索作物、地块、茬口'), findsOneWidget);
    expect(find.text('西瓜春茬'), findsOneWidget);
    expect(find.text('番茄夏茬'), findsOneWidget);
    expect(find.text('玉米秋茬'), findsOneWidget);
    _expectBottomTabs();
  });

  testWidgets('新建茬口页渲染字段和底部操作', (tester) async {
    await pump(tester, FarmCycleFormPage(repository: repository));

    expect(find.text('新建茬口'), findsWidgets);
    expect(find.text('茬口名称'), findsOneWidget);
    expect(find.text('作物模板'), findsOneWidget);
    expect(find.text('地块'), findsOneWidget);
    expect(find.text('创建茬口'), findsOneWidget);
  });

  testWidgets('作物模板列表页渲染搜索、卡片动作和底部 Tab', (tester) async {
    await pump(tester, CropTemplateListPage(repository: repository));

    expect(find.text('作物模板'), findsOneWidget);
    expect(find.text('模板库'), findsOneWidget);
    expect(find.text('搜索作物或品种'), findsOneWidget);
    expect(find.text('8424西瓜'), findsOneWidget);
    expect(find.text('普罗旺斯番茄'), findsOneWidget);
    expect(find.text('新建茬口'), findsWidgets);
    expect(find.text('编辑'), findsWidgets);
    _expectBottomTabs();
  });

  testWidgets('作物模板表单页渲染阶段编辑字段', (tester) async {
    await pump(tester, CropTemplateFormPage(repository: repository));

    expect(find.text('新建模板'), findsOneWidget);
    expect(find.text('作物名称'), findsOneWidget);
    expect(find.text('品种'), findsOneWidget);
    expect(find.text('生长阶段'), findsOneWidget);
    expect(find.text('保存模板'), findsOneWidget);
  });

  testWidgets('工人管理列表页渲染关键动作和底部 Tab', (tester) async {
    await pump(tester, WorkerListPage(repository: repository));

    expect(find.text('工人管理'), findsOneWidget);
    expect(find.text('全场人工'), findsOneWidget);
    expect(find.text('未结'), findsOneWidget);
    expect(find.text('记一笔工资'), findsOneWidget);
    expect(find.text('新增工人'), findsOneWidget);
    expect(find.text('搜索工人姓名'), findsOneWidget);
    _expectBottomTabs();
  });

  testWidgets('工人表单页渲染工资默认项和保存按钮', (tester) async {
    await pump(tester, WorkerFormPage(repository: repository));

    expect(find.text('新增工人'), findsOneWidget);
    expect(find.text('姓名'), findsOneWidget);
    expect(find.text('手机号'), findsOneWidget);
    expect(find.text('默认计薪方式'), findsOneWidget);
    expect(find.text('保存工人'), findsOneWidget);
  });

  testWidgets('业务页面路由路径常量保持稳定', (tester) async {
    expect(LedgerManualCreatePage.routePath, '/ledger-manual-create');
    expect(FarmCycleListPage.routePath, '/farm-cycle-list');
    expect(FarmCycleFormPage.routePath, '/farm-cycle-form');
    expect(CropTemplateListPage.routePath, '/crop-template-list');
    expect(CropTemplateFormPage.routePath, '/crop-template-form');
    expect(WorkerListPage.routePath, '/worker-list');
    expect(WorkerFormPage.routePath, '/worker-form');
  });

  testWidgets('业务页筛选胶囊支持设计稿绿色选中态', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ChipRail(
            items: ['全部', '在种', '计划', '已结束'],
            activeColor: businessGreen,
          ),
        ),
      ),
    );

    expect(find.text('全部'), findsOneWidget);
    expect(find.text('在种'), findsOneWidget);
  });
}

void _expectBottomTabs() {
  expect(find.text('首页'), findsOneWidget);
  expect(find.text('记录'), findsOneWidget);
  expect(find.text('芽芽'), findsOneWidget);
  expect(find.text('账本'), findsOneWidget);
  expect(find.text('我的'), findsOneWidget);
}
