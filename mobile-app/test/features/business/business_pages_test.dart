import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/business_repository.dart';
import 'package:farm_manager_app/features/business/business_ui.dart';
import 'package:farm_manager_app/features/business/business_pages.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  late RecordingAdapter adapter;
  late BusinessRepository repository;

  void setUpRepository(Map<String, Object?> overrides) {
    adapter = RecordingAdapter({
      '/cycles': paginatedCyclesResponse,
      '/crops/templates': paginatedCropTemplatesResponse,
      '/planting/workers/summary': paginatedWorkerSummariesResponse,
      'POST /costs': costRecordResponse,
      'POST /logs': logResponse,
      'POST /cycles': cycleResponse,
      'DELETE /cycles/7': {'message': 'ok'},
      'POST /crops/templates': cropTemplateResponse,
      'DELETE /crops/templates/3': {'message': 'ok'},
      'POST /planting/workers': workerResponse,
      'DELETE /planting/workers/4': {'message': 'ok'},
      'POST /planting/labor/wages': wageResponse,
      ...overrides,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    repository = BusinessRepository(ApiClient(dio: dio));
  }

  setUp(() {
    setUpRepository(const {});
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
    expect(find.text('春茬'), findsOneWidget);
    expect(find.text('番茄夏茬'), findsNothing);
    expect(find.text('玉米秋茬'), findsNothing);
    _expectBottomTabs();
  });

  testWidgets('茬口管理空数据不展示样例茬口', (tester) async {
    setUpRepository({
      '/cycles': {'items': [], 'total': 0},
    });

    await pump(tester, FarmCycleListPage(repository: repository));

    expect(find.text('还没有茬口，先新建一个生产批次。'), findsOneWidget);
    expect(find.text('在种 3'), findsNothing);
    expect(find.text('计划 1'), findsNothing);
    expect(find.text('已结束 2'), findsNothing);
    expect(find.text('西瓜春茬'), findsNothing);
    expect(find.text('番茄夏茬'), findsNothing);
    expect(find.text('玉米秋茬'), findsNothing);
  });

  testWidgets('茬口管理页长按进入多选并批量删除', (tester) async {
    await pump(tester, FarmCycleListPage(repository: repository));

    await tester.longPress(find.text('春茬'));
    await tester.pumpAndSettle();

    expect(find.text('已选 1 个'), findsOneWidget);
    expect(find.byType(Checkbox), findsOneWidget);
    expect(find.text('删除 1 项'), findsOneWidget);

    await tester.tap(find.text('删除 1 项'));
    await tester.pumpAndSettle();
    expect(find.text('删除选中的茬口？'), findsOneWidget);

    await tester.tap(find.text('确认删除'));
    await tester.pumpAndSettle();

    expect(adapter.find('DELETE', '/cycles/7').path, '/cycles/7');
    expect(find.text('已删除 1 个茬口'), findsOneWidget);
    expect(find.text('删除 1 项'), findsNothing);
  });

  testWidgets('新建茬口页渲染字段和底部操作', (tester) async {
    await pump(tester, FarmCycleFormPage(repository: repository));

    expect(find.text('新建茬口'), findsWidgets);
    expect(find.text('茬口名称'), findsOneWidget);
    expect(find.text('作物模板'), findsOneWidget);
    expect(find.text('地块'), findsOneWidget);
    expect(find.text('创建茬口'), findsOneWidget);
    expect(find.text('选择作物模板后显示阶段预览。'), findsOneWidget);
    expect(find.text('播种期'), findsNothing);
    expect(find.text('苗期'), findsNothing);
  });

  testWidgets('新建茬口页保存草稿有反馈', (tester) async {
    await pump(tester, FarmCycleFormPage(repository: repository));

    await tester.tap(find.text('保存草稿'));
    await tester.pumpAndSettle();

    expect(find.text('草稿已保留在当前页面'), findsOneWidget);
  });

  testWidgets('作物模板列表页渲染搜索、卡片动作和底部 Tab', (tester) async {
    await pump(tester, CropTemplateListPage(repository: repository));

    expect(find.text('作物模板'), findsOneWidget);
    expect(find.text('模板库'), findsOneWidget);
    expect(find.text('搜索作物或品种'), findsOneWidget);
    expect(find.text('番茄'), findsWidgets);
    expect(find.text('普罗旺斯番茄'), findsNothing);
    expect(find.text('新建茬口'), findsWidgets);
    expect(find.text('编辑'), findsWidgets);
    _expectBottomTabs();
  });

  testWidgets('作物模板空数据不展示样例模板', (tester) async {
    setUpRepository({
      '/crops/templates': {'items': [], 'total': 0},
    });

    await pump(tester, CropTemplateListPage(repository: repository));

    expect(find.text('还没有作物模板。'), findsOneWidget);
    expect(find.textContaining('已创建 6 个作物模板'), findsNothing);
    expect(find.text('8424西瓜'), findsNothing);
    expect(find.text('普罗旺斯番茄'), findsNothing);
    expect(find.text('甜玉米'), findsNothing);
  });

  testWidgets('作物模板页长按进入多选并批量删除', (tester) async {
    await pump(tester, CropTemplateListPage(repository: repository));

    await tester.longPress(find.text('番茄').first);
    await tester.pumpAndSettle();

    expect(find.text('已选 1 个'), findsOneWidget);
    expect(find.byType(Checkbox), findsOneWidget);
    expect(find.text('删除 1 项'), findsOneWidget);

    await tester.tap(find.text('删除 1 项'));
    await tester.pumpAndSettle();
    expect(find.text('删除选中的作物模板？'), findsOneWidget);

    await tester.tap(find.text('确认删除'));
    await tester.pumpAndSettle();

    expect(
      adapter.find('DELETE', '/crops/templates/3').path,
      '/crops/templates/3',
    );
    expect(find.text('已删除 1 个作物模板'), findsOneWidget);
    expect(find.text('删除 1 项'), findsNothing);
  });

  testWidgets('作物模板表单页渲染阶段编辑字段', (tester) async {
    await pump(tester, CropTemplateFormPage(repository: repository));

    expect(find.text('新建模板'), findsOneWidget);
    expect(find.text('作物名称'), findsOneWidget);
    expect(find.text('品种'), findsOneWidget);
    expect(find.text('生长阶段'), findsOneWidget);
    expect(find.text('阶段名称'), findsOneWidget);
    expect(find.text('持续天数'), findsOneWidget);
    expect(find.text('关键任务'), findsOneWidget);
    expect(find.text('保存模板'), findsOneWidget);
    expect(find.text('播种期'), findsNothing);
    expect(find.text('苗期'), findsNothing);
    expect(find.text('伸蔓期'), findsNothing);
    expect(find.text('开花坐果期'), findsNothing);
    expect(find.text('采收期'), findsNothing);
  });

  testWidgets('作物模板表单页预览和添加阶段有反馈', (tester) async {
    await pump(tester, CropTemplateFormPage(repository: repository));

    await tester.tap(find.text('预览'));
    await tester.pumpAndSettle();

    expect(find.text('已生成阶段预览'), findsOneWidget);

    await tester.ensureVisible(find.text('添加阶段'));
    await tester.tap(find.text('添加阶段'));
    await tester.pumpAndSettle();

    expect(find.text('已添加新阶段'), findsOneWidget);
  });

  testWidgets('工人管理列表页渲染关键动作和底部 Tab', (tester) async {
    await pump(tester, WorkerListPage(repository: repository));

    expect(find.text('工人管理'), findsOneWidget);
    expect(find.text('全场人工'), findsOneWidget);
    expect(find.text('未结'), findsOneWidget);
    expect(find.text('记一笔工资'), findsOneWidget);
    expect(find.text('新增工人'), findsOneWidget);
    expect(find.text('搜索工人姓名'), findsOneWidget);
    expect(find.text('张三'), findsOneWidget);
    expect(find.text('老王'), findsNothing);
    expect(find.text('老李'), findsNothing);
    _expectBottomTabs();
  });

  testWidgets('工人管理空数据不展示样例工人', (tester) async {
    setUpRepository({
      '/planting/workers/summary': {'items': [], 'total': 0},
    });

    await pump(tester, WorkerListPage(repository: repository));

    expect(find.text('还没有工人档案。'), findsOneWidget);
    expect(find.text('1,260'), findsNothing);
    expect(find.text('老王'), findsNothing);
    expect(find.text('老李'), findsNothing);
    expect(find.text('小赵'), findsNothing);
  });

  testWidgets('工人管理页长按进入多选并批量删除', (tester) async {
    await pump(tester, WorkerListPage(repository: repository));

    await tester.longPress(find.text('张三'));
    await tester.pumpAndSettle();

    expect(find.text('已选 1 个'), findsOneWidget);
    expect(find.byType(Checkbox), findsOneWidget);
    expect(find.text('删除 1 项'), findsOneWidget);

    await tester.tap(find.text('删除 1 项'));
    await tester.pumpAndSettle();
    expect(find.text('删除选中的工人档案？'), findsOneWidget);

    await tester.tap(find.text('确认删除'));
    await tester.pumpAndSettle();

    expect(
      adapter.find('DELETE', '/planting/workers/4').path,
      '/planting/workers/4',
    );
    expect(find.text('已删除 1 个工人档案'), findsOneWidget);
    expect(find.text('删除 1 项'), findsNothing);
  });

  testWidgets('工人表单页渲染工资默认项和保存按钮', (tester) async {
    await pump(tester, WorkerFormPage(repository: repository));

    expect(find.text('新增工人'), findsOneWidget);
    expect(find.text('姓名'), findsOneWidget);
    expect(find.text('手机号'), findsOneWidget);
    expect(find.text('默认计薪方式'), findsOneWidget);
    expect(find.text('保存工人'), findsOneWidget);
    expect(find.text('常用工    授粉熟练'), findsNothing);
  });

  testWidgets('农事记录页渲染字段和保存按钮', (tester) async {
    await pump(tester, FarmLogCreatePage(repository: repository));

    expect(find.text('记农事'), findsWidgets);
    expect(find.text('作业类型'), findsOneWidget);
    expect(find.text('作业日期'), findsOneWidget);
    expect(find.text('保存农事'), findsOneWidget);
  });

  testWidgets('农事记录页保存到后端', (tester) async {
    await pump(tester, FarmLogCreatePage(repository: repository));

    await tester.enterText(find.byType(TextField).at(0), '7');
    await tester.enterText(find.byType(TextField).at(1), '浇水');
    await tester.enterText(find.byType(TextField).at(2), '2026-06-10');
    await tester.enterText(find.byType(TextField).at(3), '东棚少量浇水');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    await tester.tap(find.text('保存农事'));
    await tester.pumpAndSettle();

    expect(adapter.find('POST', '/logs').data, {
      'cycle_id': 7,
      'operation_type': '浇水',
      'operation_date': '2026-06-10',
      'note': '东棚少量浇水',
    });
    expect(find.text('保存农事成功'), findsOneWidget);
  });

  testWidgets('工资记录页渲染字段和保存按钮', (tester) async {
    await pump(tester, WageCreatePage(repository: repository));

    expect(find.text('记工资'), findsWidgets);
    expect(find.text('工人姓名'), findsOneWidget);
    expect(find.text('计薪方式'), findsOneWidget);
    expect(find.text('保存工资'), findsOneWidget);
  });

  testWidgets('工资记录页保存到后端', (tester) async {
    await pump(tester, WageCreatePage(repository: repository));

    await tester.enterText(find.byType(TextField).at(0), '7');
    await tester.enterText(find.byType(TextField).at(1), '张三');
    await tester.enterText(find.byType(TextField).at(2), '浇水');
    await tester.enterText(find.byType(TextField).at(3), '2026-06-10');
    await tester.enterText(find.byType(TextField).at(4), '1');
    await tester.enterText(find.byType(TextField).at(5), '200');
    await tester.enterText(find.byType(TextField).at(6), '0');
    await tester.enterText(find.byType(TextField).at(7), '今日浇水工资');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    await tester.tap(find.text('保存工资'));
    await tester.pumpAndSettle();

    final request = adapter.find('POST', '/planting/labor/wages');
    expect(request.data, containsPair('cycle_id', 7));
    expect(request.data, containsPair('worker_name', '张三'));
    expect(request.data, containsPair('operation_type', '浇水'));
    expect(request.data, containsPair('work_date', '2026-06-10'));
    expect(request.data, containsPair('quantity', 1));
    expect(request.data, containsPair('unit_price', 200));
    expect(request.data, containsPair('paid_amount', 0));
    expect(request.data, containsPair('pay_type', 'daily'));
    expect(request.data, contains('client_request_id'));
    expect(find.text('保存工资成功'), findsOneWidget);
  });

  testWidgets('工人管理页记工资入口进入工资记录页', (tester) async {
    await pump(tester, WorkerListPage(repository: repository));

    await tester.tap(find.text('记一笔工资'));
    await tester.pumpAndSettle();

    expect(find.text('保存工资'), findsOneWidget);
    expect(find.text('工人姓名'), findsOneWidget);
  });

  testWidgets('表单取消按钮可返回上一页', (tester) async {
    await pump(tester, WorkerListPage(repository: repository));

    await tester.tap(find.text('新增工人'));
    await tester.pumpAndSettle();
    expect(find.text('保存工人'), findsOneWidget);

    await tester.tap(find.text('取消'));
    await tester.pumpAndSettle();

    expect(find.text('保存工人'), findsNothing);
    expect(find.text('工人管理'), findsOneWidget);
  });

  testWidgets('茬口卡片可进入农事记录页并可触发账本导航', (tester) async {
    var selectedIndex = -1;
    await pump(
      tester,
      FarmCycleListPage(
        repository: repository,
        onBottomTabChanged: (index) => selectedIndex = index,
      ),
    );

    await tester.ensureVisible(find.text('记农事').first);
    await tester.tap(find.text('记农事').first);
    await tester.pumpAndSettle();

    expect(find.text('保存农事'), findsOneWidget);

    await tester.tap(find.byType(HeaderIconButton).first);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('查看账本').first);
    await tester.tap(find.text('查看账本').first);

    expect(selectedIndex, 3);
  });

  testWidgets('业务页面路由路径常量保持稳定', (tester) async {
    expect(LedgerManualCreatePage.routePath, '/ledger-manual-create');
    expect(FarmCycleListPage.routePath, '/farm-cycle-list');
    expect(FarmCycleFormPage.routePath, '/farm-cycle-form');
    expect(CropTemplateListPage.routePath, '/crop-template-list');
    expect(CropTemplateFormPage.routePath, '/crop-template-form');
    expect(WorkerListPage.routePath, '/worker-list');
    expect(WorkerFormPage.routePath, '/worker-form');
    expect(FarmLogCreatePage.routePath, '/farm-log-create');
    expect(WageCreatePage.routePath, '/wage-create');
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
