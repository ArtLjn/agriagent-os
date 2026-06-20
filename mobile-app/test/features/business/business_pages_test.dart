import 'dart:async';
import 'dart:collection';

import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/business_repository.dart';
import 'package:farm_manager_app/features/business/business_ui.dart';
import 'package:farm_manager_app/features/business/business_pages.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  late RecordingAdapter adapter;
  late BusinessRepository repository;

  void setUpRepository(Map<String, Object?> overrides) {
    adapter = RecordingAdapter({
      '/cycles': paginatedCyclesResponse,
      '/cost-categories': [categoryResponse, customCategoryResponse],
      '/crops/templates': paginatedCropTemplatesResponse,
      '/planting/workers/summary': paginatedWorkerSummariesResponse,
      'POST /costs': costRecordResponse,
      'POST /cost-categories': customCategoryResponse,
      'DELETE /cost-categories/2': {'message': 'ok'},
      'POST /logs': logResponse,
      'POST /cycles': cycleResponse,
      'PUT /cycles/7': cycleResponse,
      'POST /planting/units': plantingUnitResponse,
      'DELETE /cycles/7': {'message': 'ok'},
      'POST /crops/templates': cropTemplateResponse,
      'PUT /crops/templates/3': cropTemplateResponse,
      'DELETE /crops/templates/3': {'message': 'ok'},
      'POST /planting/workers': workerResponse,
      'PUT /planting/workers/4': workerResponse,
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

  Finder rowFor(String label) {
    return find.ancestor(
      of: find.text(label),
      matching: find.byType(InkWell),
    );
  }

  void expectRowChevron(String label, Matcher matcher) {
    expect(
      find.descendant(
        of: rowFor(label),
        matching: find.byIcon(LucideIcons.chevronRight),
      ),
      matcher,
    );
  }

  testWidgets('记账手动填写页渲染表单字段和保存按钮', (tester) async {
    await pump(tester, LedgerManualCreatePage(repository: repository));

    expect(find.text('记账'), findsWidgets);
    expect(find.text('收入'), findsOneWidget);
    expect(find.text('支出'), findsOneWidget);
    expect(find.text('金额'), findsOneWidget);
    expect(find.text('日期'), findsOneWidget);
    expect(find.text('备注'), findsOneWidget);
    expect(find.text('关联茬口'), findsNothing);
    expect(find.text('交易对象'), findsNothing);
    expect(find.text('保存记录'), findsOneWidget);
  });

  testWidgets('记账页使用分类下拉并按后端账务字段保存', (tester) async {
    await pump(tester, LedgerManualCreatePage(repository: repository));

    await tester.tap(find.byKey(const Key('ledger-category-dropdown-search')));
    await tester.pumpAndSettle();
    final categoryOption = find.byKey(const Key('ledger-category-option-肥料'));
    await tester
        .tapAt(tester.getTopLeft(categoryOption) + const Offset(24, 24));
    await tester.pumpAndSettle();

    await tester.enterText(find.widgetWithText(TextField, '输入金额'), '200');
    await tester.tap(find.text('保存记录'));
    await tester.pumpAndSettle();

    final request = adapter.find('POST', '/costs');
    final data = request.data! as Map<String, dynamic>;
    expect(data, containsPair('record_type', 'cost'));
    expect(data, containsPair('category', '肥料'));
    expect(data, containsPair('amount', 200));
    expect(data, containsPair('settled_amount', 200));
    expect(data, containsPair('record_date', _todayTextForTest()));
    expect('${data['recorded_at']}', startsWith(_todayTextForTest()));
    expect(data, isNot(contains('cycle_id')));
    expect(data, isNot(contains('counterparty')));
    expect(data, isNot(contains('source_type')));
    expect(data, isNot(contains('parent_record_id')));
    expect(data, isNot(contains('due_date')));
    expect(find.widgetWithText(TextField, '输入金额'), findsOneWidget);
    expect(find.text('200'), findsNothing);
    expect(find.text('保存记录成功'), findsOneWidget);
  });

  testWidgets('记账页保存中禁用按钮防止重复提交', (tester) async {
    final completer = Completer<Object?>();
    setUpRepository({
      'POST /costs': completer.future,
    });
    await pump(tester, LedgerManualCreatePage(repository: repository));

    await tester.tap(find.byKey(const Key('ledger-category-dropdown-search')));
    await tester.pumpAndSettle();
    final categoryOption = find.byKey(const Key('ledger-category-option-肥料'));
    await tester
        .tapAt(tester.getTopLeft(categoryOption) + const Offset(24, 24));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, '输入金额'), '200');

    await tester.tap(find.text('保存记录'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 1));
    final requestCountAfterFirstTap = adapter.requests
        .where(
            (request) => request.method == 'POST' && request.path == '/costs')
        .length;
    await tester.tap(find.text('保存中'), warnIfMissed: false);
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(requestCountAfterFirstTap, 1);
    expect(
      adapter.requests
          .where(
              (request) => request.method == 'POST' && request.path == '/costs')
          .length,
      1,
    );

    completer.complete(costRecordResponse);
    await tester.pumpAndSettle();

    expect(find.text('保存记录'), findsOneWidget);
  });

  testWidgets('记账页可进入分类管理页', (tester) async {
    await pump(tester, LedgerManualCreatePage(repository: repository));

    await tester.tap(find.text('管理'));
    await tester.pumpAndSettle();

    expect(find.text('分类管理'), findsWidgets);
    expect(find.text('分类列表'), findsOneWidget);
  });

  testWidgets('分类管理页支持新增自定义分类', (tester) async {
    await pump(tester, LedgerCategoryManagementPage(repository: repository));

    expect(find.text('肥料'), findsOneWidget);
    expect(find.text('人工工资'), findsOneWidget);

    await tester.tap(find.text('新增分类').last);
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, '输入分类名称'), '水电');
    await tester.tap(find.text('保存分类'));
    await tester.pumpAndSettle();

    final request = adapter.find('POST', '/cost-categories');
    final data = request.data! as Map<String, dynamic>;
    expect(data, containsPair('name', '水电'));
    expect(data, containsPair('type', 'cost'));
  });

  testWidgets('记账页从分类管理返回后刷新分类下拉', (tester) async {
    setUpRepository({
      '/cost-categories': ListQueue<Object?>.from([
        [categoryResponse],
        [categoryResponse],
        [categoryResponse, waterElectricCategoryResponse],
      ]),
    });
    await pump(tester, LedgerManualCreatePage(repository: repository));

    await tester.tap(find.text('管理'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('新增分类').last);
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, '输入分类名称'), '水电');
    await tester.tap(find.text('保存分类'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('返回'));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('ledger-category-dropdown-search')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('ledger-category-option-水电')), findsOneWidget);
  });

  testWidgets('记账页日期行使用日期时间选择器', (tester) async {
    await pump(tester, LedgerManualCreatePage(repository: repository));

    await tester
        .ensureVisible(find.byKey(const ValueKey('ledger-datetime-row')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('ledger-datetime-row')));
    await tester.pumpAndSettle();

    expect(find.byType(DatePickerDialog), findsOneWidget);

    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();

    expect(find.byType(TimePickerDialog), findsOneWidget);
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
    expect(find.text('种植区域'), findsOneWidget);
    expect(find.text('区域面积'), findsOneWidget);
    expect(find.text('创建茬口'), findsOneWidget);
    expect(find.text('选择作物模板后显示阶段预览。'), findsOneWidget);
    expect(find.text('播种期'), findsNothing);
    expect(find.text('苗期'), findsNothing);
  });

  testWidgets('新建茬口选择模板后创建茬口和种植区域', (tester) async {
    await pump(tester, FarmCycleFormPage(repository: repository));

    await tester.tap(find.byKey(const Key('template-dropdown-search')));
    await tester.pumpAndSettle();
    final templateOption = find.byKey(
      const Key('template-option-番茄 / 粉果 306'),
    );
    await tester.tapAt(
      tester.getTopLeft(templateOption) + const Offset(24, 24),
    );
    await tester.pumpAndSettle();

    await tester.enterText(
      find.widgetWithText(TextField, '例：东大棚 1 号、A 区'),
      '东大棚 1 号',
    );
    await tester.enterText(find.widgetWithText(TextField, '输入亩数'), '19');
    await tester.tap(find.text('创建茬口'));
    await tester.pumpAndSettle();

    final cycleRequest = adapter.find('POST', '/cycles');
    expect(cycleRequest.data, containsPair('crop_template_id', 3));
    expect(cycleRequest.data, containsPair('field_name', '东大棚 1 号'));
    expect(cycleRequest.data, containsPair('total_area_mu', 19));

    final unitRequest = adapter.find('POST', '/planting/units');
    expect(unitRequest.data, containsPair('cycle_id', 7));
    expect(unitRequest.data, containsPair('name', '东大棚 1 号'));
    expect(unitRequest.data, containsPair('area_mu', 19));
  });

  testWidgets('新建茬口页保存草稿有反馈', (tester) async {
    await pump(tester, FarmCycleFormPage(repository: repository));

    await tester.tap(find.text('保存草稿'));
    await tester.pumpAndSettle();

    expect(find.text('草稿已保留在当前页面'), findsOneWidget);
  });

  testWidgets('茬口编辑页回填基础字段并保存', (tester) async {
    await pump(tester, FarmCycleListPage(repository: repository));

    final editButton = find.widgetWithText(FilledActionButton, '编辑');
    await tester.ensureVisible(editButton);
    await tester.tap(editButton);
    await tester.pumpAndSettle();

    expect(find.text('编辑茬口'), findsOneWidget);
    expect(find.widgetWithText(TextField, '春茬'), findsOneWidget);
    expect(find.widgetWithText(TextField, '一号棚'), findsOneWidget);

    await tester.enterText(find.widgetWithText(TextField, '春茬'), '春茬更新');
    await tester.tap(find.text('保存茬口'));
    await tester.pumpAndSettle();

    final request = adapter.find('PUT', '/cycles/7');
    expect(request.data, containsPair('name', '春茬更新'));
    expect(request.data, containsPair('field_name', '一号棚'));
    expect(request.data, containsPair('total_area_mu', 3.5));
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

  testWidgets('作物模板列表支持搜索和分类筛选', (tester) async {
    setUpRepository({
      '/crops/templates': cropTemplateFilterResponse,
    });

    await pump(tester, CropTemplateListPage(repository: repository));

    await tester.enterText(find.byType(TextField), '8424');
    await tester.pumpAndSettle();

    expect(find.text('西瓜'), findsOneWidget);
    expect(find.text('番茄'), findsNothing);
    expect(find.text('玉米'), findsNothing);

    await tester.enterText(find.byType(TextField), '');
    await tester.pumpAndSettle();
    await tester.tap(find.text('蔬菜'));
    await tester.pumpAndSettle();

    expect(find.text('番茄'), findsWidgets);
    expect(find.text('西瓜'), findsNothing);
    expect(find.text('玉米'), findsNothing);

    await tester.tap(find.text('粮食'));
    await tester.pumpAndSettle();

    expect(find.text('玉米'), findsOneWidget);
    expect(find.text('番茄'), findsNothing);
    expect(find.text('西瓜'), findsNothing);
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
    expect(find.text('模板信息'), findsOneWidget);
    expect(find.text('保存后可复用'), findsOneWidget);
    expect(find.text('输入作物名称，生成阶段'), findsNothing);
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

  testWidgets('作物模板表单按接口字段保存且作物名称品种为输入框', (tester) async {
    await pump(tester, CropTemplateFormPage(repository: repository));

    expect(find.byIcon(LucideIcons.chevronRight), findsNothing);

    await tester.enterText(find.widgetWithText(TextField, '输入作物名称'), '黄瓜');
    await tester.enterText(find.widgetWithText(TextField, '输入品种'), '津优');
    await tester.enterText(find.widgetWithText(TextField, '输入阶段名称'), '苗期');
    await tester.enterText(find.widgetWithText(TextField, '输入天数'), '12');
    await tester.enterText(find.widgetWithText(TextField, '输入关键任务'), '控水');
    await tester.drag(find.byType(Scrollable).first, const Offset(0, -360));
    await tester.pumpAndSettle();
    await tester.tap(find.text('添加阶段'));
    await tester.pumpAndSettle();
    await tester.enterText(
        find.widgetWithText(TextField, '输入阶段名称').last, '采收期');
    await tester.enterText(find.widgetWithText(TextField, '输入天数').last, '28');
    await tester.enterText(
        find.widgetWithText(TextField, '输入关键任务').last, '分批采收');
    await tester.tap(find.text('保存模板'));
    await tester.pumpAndSettle();

    final request = adapter.find('POST', '/crops/templates');
    expect(request.data, containsPair('name', '黄瓜'));
    expect(request.data, containsPair('variety', '津优'));
    expect(request.data, contains('stages'));
    final data = request.data! as Map<String, dynamic>;
    final stages = data['stages'] as List<dynamic>;
    expect(stages, hasLength(2));
    expect(stages.first, containsPair('name', '苗期'));
    expect(stages.first, containsPair('duration_days', 12));
    expect(stages.first, containsPair('order_index', 1));
    expect(stages.first, containsPair('key_tasks', '控水'));
    expect(stages.last, containsPair('name', '采收期'));
    expect(stages.last, containsPair('duration_days', 28));
    expect(stages.last, containsPair('order_index', 2));
    expect(stages.last, containsPair('key_tasks', '分批采收'));
  });

  testWidgets('作物模板编辑更新当前模板', (tester) async {
    await pump(tester, CropTemplateListPage(repository: repository));

    final editButton = find.widgetWithText(FilledActionButton, '编辑');
    await tester.ensureVisible(editButton);
    await tester.tap(editButton);
    await tester.pumpAndSettle();

    expect(find.text('编辑模板'), findsOneWidget);
    expect(find.widgetWithText(TextField, '番茄'), findsOneWidget);
    expect(find.widgetWithText(TextField, '粉果 306'), findsOneWidget);

    await tester.enterText(find.widgetWithText(TextField, '番茄'), '樱桃番茄');
    await tester.tap(find.text('保存模板'));
    await tester.pumpAndSettle();

    final request = adapter.find('PUT', '/crops/templates/3');
    expect(request.data, containsPair('name', '樱桃番茄'));
    expect(request.data, containsPair('variety', '粉果 306'));
  });

  testWidgets('作物模板快捷新建茬口预选当前模板', (tester) async {
    await pump(tester, CropTemplateListPage(repository: repository));

    final createCycleButton = find.widgetWithText(FilledActionButton, '新建茬口');
    await tester.ensureVisible(createCycleButton);
    await tester.tap(createCycleButton);
    await tester.pumpAndSettle();

    expect(find.text('新建茬口'), findsWidgets);
    expect(find.text('番茄'), findsWidgets);

    await tester.enterText(find.widgetWithText(TextField, '输入茬口名称'), '番茄春茬');
    await tester.enterText(
      find.widgetWithText(TextField, '例：东大棚 1 号、A 区'),
      '东大棚 1 号',
    );
    await tester.ensureVisible(find.text('创建茬口'));
    await tester.tap(find.text('创建茬口'));
    await tester.pumpAndSettle();

    final request = adapter.find('POST', '/cycles');
    expect(request.data, containsPair('name', '番茄春茬'));
    expect(request.data, containsPair('crop_template_id', 3));
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

  testWidgets('工人管理默认只展示在职工人并将停用显示为离职', (tester) async {
    setUpRepository({
      '/planting/workers/summary': workerSummaryFilterResponse,
    });

    await pump(tester, WorkerListPage(repository: repository));

    expect(find.text('张三'), findsOneWidget);
    expect(find.text('李四'), findsOneWidget);
    expect(find.text('老王'), findsNothing);
    expect(find.text('离职'), findsOneWidget);
    expect(find.text('停用'), findsNothing);
  });

  testWidgets('工人管理支持姓名搜索和标签筛选', (tester) async {
    setUpRepository({
      '/planting/workers/summary': workerSummaryFilterResponse,
    });

    await pump(tester, WorkerListPage(repository: repository));

    await tester.enterText(find.byType(TextField), '李');
    await tester.pumpAndSettle();

    expect(find.text('李四'), findsOneWidget);
    expect(find.text('张三'), findsNothing);

    await tester.enterText(find.byType(TextField), '');
    await tester.pumpAndSettle();
    await tester.tap(find.text('有欠款'));
    await tester.pumpAndSettle();

    expect(find.text('李四'), findsOneWidget);
    expect(find.text('张三'), findsNothing);
    expect(find.text('老王'), findsNothing);

    await tester.tap(find.text('已结清'));
    await tester.pumpAndSettle();

    expect(find.text('张三'), findsOneWidget);
    expect(find.text('李四'), findsNothing);
    expect(find.text('老王'), findsNothing);

    await tester.tap(find.text('离职'));
    await tester.pumpAndSettle();

    expect(find.text('老王'), findsOneWidget);
    expect(find.text('张三'), findsNothing);
    expect(find.text('李四'), findsNothing);
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
    expect(find.text('在用'), findsOneWidget);
    expect(find.text('离职'), findsOneWidget);
    expect(find.text('常用工    授粉熟练'), findsNothing);
  });

  testWidgets('工人编辑页可设置离职状态并保存', (tester) async {
    await pump(tester, WorkerListPage(repository: repository));

    await tester.tap(find.text('编辑'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('离职'));
    await tester.enterText(find.widgetWithText(TextField, '张三'), '张三丰');
    await tester.tap(find.text('保存工人'));
    await tester.pumpAndSettle();

    final request = adapter.find('PUT', '/planting/workers/4');
    expect(request.data, containsPair('name', '张三丰'));
    expect(request.data, containsPair('status', 'inactive'));
  });

  testWidgets('农事记录页渲染字段和保存按钮', (tester) async {
    await pump(tester, FarmLogCreatePage(repository: repository));

    expect(find.text('记农事'), findsWidgets);
    expect(find.text('选择茬口'), findsOneWidget);
    expect(find.text('输入茬口 ID'), findsNothing);
    expect(find.text('作业类型'), findsOneWidget);
    expect(find.text('作业时间'), findsOneWidget);
    expect(find.text('作业日期'), findsNothing);
    expect(find.text('图片链接'), findsNothing);
    expect(find.text('保存农事'), findsOneWidget);
  });

  testWidgets('农事记录页只展示核心字段且选择型字段有箭头', (tester) async {
    await pump(tester, FarmLogCreatePage(repository: repository));

    expect(find.text('关联茬口'), findsOneWidget);
    expect(find.text('作业类型'), findsOneWidget);
    expect(find.text('作业时间'), findsOneWidget);
    expect(find.text('备注'), findsOneWidget);
    expect(find.text('作业日期'), findsNothing);
    expect(find.text('图片链接'), findsNothing);

    expect(find.byKey(const Key('cycle-dropdown-search')), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('cycle-dropdown-search')),
        matching: find.byIcon(LucideIcons.chevronDown),
      ),
      findsOneWidget,
    );
    expectRowChevron('作业类型', findsNothing);
    expectRowChevron('备注', findsNothing);
    expect(
        find.descendant(
          of: find.byKey(const ValueKey('farm-log-datetime-card')),
          matching: find.byIcon(LucideIcons.chevronRight),
        ),
        findsOneWidget);
  });

  testWidgets('农事记录页保存到后端', (tester) async {
    await pump(tester, FarmLogCreatePage(repository: repository));

    await tester.tap(find.byKey(const Key('cycle-dropdown-search')));
    await tester.pumpAndSettle();
    final farmLogCycleOption = find.byKey(const Key('cycle-option-春茬'));
    await tester.tapAt(
      tester.getTopLeft(farmLogCycleOption) + const Offset(24, 24),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), '浇水');
    final selectedDateText =
        tester.widget<Text>(find.byKey(const ValueKey('farm-log-date-text')));
    final selectedTimeText =
        tester.widget<Text>(find.byKey(const ValueKey('farm-log-time-text')));
    final dateText = selectedDateText.data!;
    final timeText = selectedTimeText.data!;
    await tester.ensureVisible(find.text('作业时间'));
    await tester.tap(find.text('作业时间'));
    await tester.pumpAndSettle();
    expect(find.text('选择作业日期'), findsOneWidget);
    await tester.tap(find.text('取消').last);
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(1), '东棚少量浇水');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    await tester.tap(find.text('保存农事'));
    await tester.pumpAndSettle();

    expect(adapter.find('POST', '/logs').data, {
      'cycle_id': 7,
      'operation_type': '浇水',
      'operation_date': dateText,
      'operation_time': '${dateText}T$timeText:00',
      'note': '东棚少量浇水',
    });
    expect(find.text('保存农事成功'), findsOneWidget);
  });

  testWidgets('工资记录页渲染字段和保存按钮', (tester) async {
    await pump(tester, WageCreatePage(repository: repository));

    expect(find.text('记工资'), findsWidgets);
    expect(find.text('选择茬口'), findsOneWidget);
    expect(find.text('输入茬口 ID'), findsNothing);
    expect(find.text('工人姓名'), findsOneWidget);
    expect(find.text('计薪方式'), findsOneWidget);
    expect(find.text('保存工资'), findsOneWidget);
  });

  testWidgets('工资记录页工人和作业时间字段都有具体选择器', (tester) async {
    await pump(tester, WageCreatePage(repository: repository));

    await tester.tap(find.byKey(const Key('worker-dropdown-search')));
    await tester.pumpAndSettle();
    final workerOption = find.byKey(const Key('worker-option-张三'));
    expect(workerOption, findsOneWidget);
    await tester.tapAt(
      tester.getTopLeft(workerOption) + const Offset(24, 24),
    );
    await tester.pumpAndSettle();
    await tester.pump(const Duration(milliseconds: 250));
    expect(find.text('张三'), findsOneWidget);

    await pump(tester, WageCreatePage(repository: repository));
    expect(find.byKey(const ValueKey('wage-datetime-row')), findsOneWidget);
    expect(find.text('作业时间'), findsOneWidget);
    expect(find.text(_todayTextForTest()), findsOneWidget);
    final timeText =
        tester.widget<Text>(find.byKey(const ValueKey('wage-time-text'))).data!;
    expect(timeText, matches(RegExp(r'^\d{2}:\d{2}$')));

    final wageDateTimeRow = find.byKey(const ValueKey('wage-datetime-row'));
    await tester.ensureVisible(wageDateTimeRow);
    await tester.tapAt(
      tester.getTopLeft(wageDateTimeRow) + const Offset(24, 24),
    );
    await tester.pumpAndSettle();
    expect(find.text('选择作业日期'), findsOneWidget);
    await tester.tap(find.text('取消').last);
    await tester.pumpAndSettle();
  });

  testWidgets('工资记录页保存到后端', (tester) async {
    await pump(tester, WageCreatePage(repository: repository));

    await tester.tap(find.byKey(const Key('cycle-dropdown-search')));
    await tester.pumpAndSettle();
    final wageCycleOption = find.byKey(const Key('cycle-option-春茬'));
    await tester.tapAt(
      tester.getTopLeft(wageCycleOption) + const Offset(24, 24),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('worker-dropdown-search')));
    await tester.pumpAndSettle();
    final workerOption = find.byKey(const Key('worker-option-张三'));
    await tester.tapAt(
      tester.getTopLeft(workerOption) + const Offset(24, 24),
    );
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), '浇水');
    final workDate =
        tester.widget<Text>(find.byKey(const ValueKey('wage-date-text'))).data!;
    final workTime =
        tester.widget<Text>(find.byKey(const ValueKey('wage-time-text'))).data!;
    await tester.enterText(find.byType(TextField).at(1), '1');
    await tester.enterText(find.byType(TextField).at(2), '200');
    await tester.enterText(find.byType(TextField).at(3), '0');
    await tester.enterText(find.byType(TextField).at(4), '今日浇水工资');
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    await tester.tap(find.text('保存工资'));
    await tester.pumpAndSettle();

    final request = adapter.find('POST', '/planting/labor/wages');
    expect(request.data, containsPair('cycle_id', 7));
    expect(request.data, containsPair('worker_name', '张三'));
    expect(request.data, containsPair('operation_type', '浇水'));
    expect(request.data, containsPair('work_date', workDate));
    expect(
      request.data,
      containsPair('recorded_at', '${workDate}T$workTime:00.000'),
    );
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

String _todayTextForTest() {
  final now = DateTime.now();
  final month = now.month.toString().padLeft(2, '0');
  final day = now.day.toString().padLeft(2, '0');
  return '${now.year}-$month-$day';
}
