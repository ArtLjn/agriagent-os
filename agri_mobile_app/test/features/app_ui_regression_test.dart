import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/api/api_models.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/business_repository.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/features/auth/onboarding_setup_screen.dart';
import 'package:farm_manager_app/features/billing/billing_controller.dart';
import 'package:farm_manager_app/features/billing/billing_screen.dart';
import 'package:farm_manager_app/features/business/business_pages.dart';
import 'package:farm_manager_app/features/home/advice_detail_screen.dart';
import 'package:farm_manager_app/features/home/home_controller.dart';
import 'package:farm_manager_app/features/profile/profile_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_ai_confirm_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_flow_controller.dart';
import 'package:farm_manager_app/features/record_flow/record_manual_edit_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_save_success_screen.dart';
import 'package:farm_manager_app/features/shell/app_shell.dart';
import 'package:farm_manager_app/features/shell/bottom_tab_bar.dart';
import 'package:farm_manager_app/features/workbench/workbench_screen.dart';
import 'package:farm_manager_app/features/yaya/yaya_screen.dart';
import 'package:farm_manager_app/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../support/api_test_fixtures.dart';
import '../support/fake_app_dependencies.dart';

void main() {
  late FakeAppDependencies dependencies;
  late RecordFlowController controller;
  const draft = RecordDraft(
      scene: 'ledger.record',
      originalText: '今天买肥料200元',
      fields: {'amount': '200', 'category': '肥料'},
      missingFields: [],
      warnings: []);

  setUp(() {
    dependencies = FakeAppDependencies();
    controller = RecordFlowController(
        workbench: dependencies.workbench, billing: dependencies.billing);
  });

  Future<void> pumpPage(WidgetTester tester, Widget page,
      {double width = 390, double scale = 1}) async {
    tester.view.physicalSize = Size(width, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final previousErrorHandler = FlutterError.onError;
    final errors = <String>[];
    FlutterError.onError = (details) {
      errors.add(details.toString());
      previousErrorHandler?.call(details);
    };
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light(),
      builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: TextScaler.linear(scale)),
          child: child!),
      home: page,
    ));
    await tester.pumpAndSettle();
    FlutterError.onError = previousErrorHandler;
    expect(errors, isEmpty);
  }

  final pages = <String, Widget Function()>{
    for (var index = 0; index < 5; index++)
      '主导航 $index': () =>
          AppShell(dependencies: dependencies, initialIndex: index),
    '首次设置': () => OnboardingSetupScreen(
        onStart: () {},
        onSkip: () {},
        profile: dependencies.profile,
        location: dependencies.location,
        locations: dependencies.locations),
    '茬口列表': () => FarmCycleListPage(repository: dependencies.business),
    '新建茬口': () => FarmCycleFormPage(repository: dependencies.business),
    '编辑茬口': () => FarmCycleFormPage(
        repository: dependencies.business,
        cycleId: 7,
        initialRecord: ApiRecord.fromJson(cycleResponse)),
    '模板列表': () => CropTemplateListPage(repository: dependencies.business),
    '新建模板': () => CropTemplateFormPage(repository: dependencies.business),
    '编辑模板': () => CropTemplateFormPage(
        repository: dependencies.business,
        templateId: 3,
        initialRecord: ApiRecord.fromJson(cropTemplateResponse)),
    '工人列表': () => WorkerListPage(repository: dependencies.business),
    '新增工人': () => WorkerFormPage(repository: dependencies.business),
    '编辑工人': () => WorkerFormPage(
        repository: dependencies.business,
        workerId: 9,
        initialRecord: ApiRecord.fromJson(workerResponse)),
    '记农事': () => FarmLogCreatePage(repository: dependencies.business),
    '记账': () => LedgerManualCreatePage(repository: dependencies.business),
    '分类管理': () =>
        LedgerCategoryManagementPage(repository: dependencies.business),
    '记工资': () => WageCreatePage(repository: dependencies.business),
    '记录确认': () => RecordAiConfirmScreen(controller: controller, draft: draft),
    '记录编辑': () => RecordManualEditScreen(controller: controller, draft: draft),
    '记录成功': () => const RecordSaveSuccessScreen(
        result: RecordSaveResult(
            label: '已同步到账本', json: {'category': '肥料', 'amount': 200})),
    '建议详情': () => const AdviceDetailScreen(
        suggestion: HomeSuggestionViewModel(
            title: '安排田间作业', subtitle: '结合天气和生产阶段，安排接下来的田间工作。')),
    '技能列表': () => YayaSkillsPage(repository: dependencies.yaya),
    '关于': () => const AboutAppPage(),
  };

  for (final entry in pages.entries) {
    for (final viewport in [(390.0, 1.0), (320.0, 1.3)]) {
      testWidgets('${entry.key}在宽度${viewport.$1}、字号${viewport.$2}下可滚动且无溢出',
          (tester) async {
        await pumpPage(tester, entry.value(),
            width: viewport.$1, scale: viewport.$2);
        expect(tester.takeException(), isNull);
        final scrollViews = find.byType(SingleChildScrollView);
        if (scrollViews.evaluate().isNotEmpty) {
          await tester.drag(scrollViews.first, const Offset(0, -500));
          await tester.pumpAndSettle();
          expect(tester.takeException(), isNull);
        }
      });
    }
  }

  testWidgets('连续切换主导航保留聊天草稿、控制器与页面滚动位置', (tester) async {
    await pumpPage(
        tester, AppShell(dependencies: dependencies, initialIndex: 2));
    final draftController =
        tester.widget<TextField>(find.byType(TextField)).controller;
    await tester.enterText(find.byType(TextField), '明天安排采收，先留在草稿里');
    final bar = find.byType(AppBottomTabBar);
    Finder tab(String label) =>
        find.descendant(of: bar, matching: find.text(label));
    await tester.tap(tab('我的'));
    await tester.pump(const Duration(milliseconds: 40));
    await tester.tap(tab('记录'));
    await tester.pump(const Duration(milliseconds: 30));
    await tester.tap(tab('芽芽'));
    await tester.pumpAndSettle();
    expect(tester.widget<TextField>(find.byType(TextField)).controller,
        same(draftController));
    expect(draftController!.text, '明天安排采收，先留在草稿里');
    expect(
        tester
            .widget<FadeTransition>(find.byKey(const ValueKey('main-tab-fade')))
            .opacity
            .value,
        1);
    await tester.tap(tab('记录'));
    await tester.pumpAndSettle();
    final scroller = find
        .descendant(
            of: find.byType(WorkbenchScreen), matching: find.byType(Scrollable))
        .first;
    await tester.drag(scroller, const Offset(0, -400));
    await tester.pumpAndSettle();
    final scrollState = tester.state<ScrollableState>(scroller);
    final offset = scrollState.position.pixels;
    expect(offset, greaterThan(0));
    await tester.tap(tab('首页'));
    await tester.pumpAndSettle();
    await tester.tap(tab('记录'));
    await tester.pumpAndSettle();
    expect(tester.state<ScrollableState>(scroller), same(scrollState));
    expect(scrollState.position.pixels, offset);
    expect(tester.takeException(), isNull);
  });

  testWidgets('二级页面进入和返回动效都能完成，动画结束后不残留位移', (tester) async {
    late MaterialPageRoute<void> route;
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light().copyWith(platform: TargetPlatform.android),
      home: Builder(
          builder: (context) => Scaffold(
                  body: TextButton(
                onPressed: () {
                  route =
                      MaterialPageRoute(builder: (_) => const AboutAppPage());
                  Navigator.of(context).push(route);
                },
                child: const Text('打开关于'),
              ))),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.text('打开关于'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 70));
    final fade = find.byKey(const ValueKey('page-route-fade')).last;
    final slide = find.byKey(const ValueKey('page-route-slide')).last;
    expect(tester.widget<FadeTransition>(fade).opacity.value,
        inExclusiveRange(0, 1));
    expect(tester.widget<SlideTransition>(slide).position.value.dx,
        greaterThan(0));
    await tester.pumpAndSettle();
    expect(tester.widget<FadeTransition>(fade).opacity.value, 1);
    expect(tester.widget<SlideTransition>(slide).position.value, Offset.zero);
    expect(route.transitionDuration, AppMotion.pageDuration);
    expect(route.reverseTransitionDuration, AppMotion.exitDuration);
    Navigator.of(tester.element(find.byType(AboutAppPage))).pop();
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 120));
    expect(tester.widget<FadeTransition>(fade).opacity.value,
        inExclusiveRange(0, 1));
    await tester.pumpAndSettle();
    expect(find.byType(AboutAppPage), findsNothing);
    expect(find.text('打开关于'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('减少动画设置下导航、页面和弹层直接切换', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light().copyWith(platform: TargetPlatform.android),
      builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(disableAnimations: true),
          child: child!),
      home: AppShell(dependencies: dependencies),
    ));
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(
        of: find.byType(AppBottomTabBar), matching: find.text('我的')));
    await tester.pump();
    expect(
        tester
            .widget<FadeTransition>(find.byKey(const ValueKey('main-tab-fade')))
            .opacity
            .value,
        1);
    expect(
        tester
            .widget<SlideTransition>(
                find.byKey(const ValueKey('main-tab-slide')))
            .position
            .value,
        Offset.zero);
    expect(
        tester
            .widget<AnimatedPositioned>(
                find.byKey(const ValueKey('tab-active-indicator')))
            .duration,
        Duration.zero);
    expect(
        AppMotion.sheetStyle(tester.element(find.byType(ProfileScreen)))
            .duration,
        Duration.zero);
    await tester.ensureVisible(find.text('关于田掌柜'));
    await tester.tap(find.text('关于田掌柜'));
    await tester.pump();
    await tester.pump();
    expect(find.byType(AboutAppPage), findsOneWidget);
    expect(find.byKey(const ValueKey('page-route-fade')), findsNothing);
    expect(tester.takeException(), isNull);
    await tester.pumpAndSettle();
  });

  testWidgets('记录页保留实际入口并且不展示虚构经营数字', (tester) async {
    await pumpPage(
        tester, AppShell(dependencies: dependencies, initialIndex: 1));
    expect(find.text('手动记一笔'), findsOneWidget);
    expect(find.text('今日概览'), findsNothing);
    expect(find.text('1,280'), findsNothing);
    expect(find.textContaining('本周12条'), findsNothing);
    await tester.tap(find.text('手动记一笔'));
    await tester.pumpAndSettle();
    expect(find.text('保存记录'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('账本记一笔按钮打开真实记账表单并可返回', (tester) async {
    await pumpPage(
        tester, AppShell(dependencies: dependencies, initialIndex: 3));
    await tester.tap(find.text('记一笔'));
    await tester.pumpAndSettle();
    expect(find.text('保存记录'), findsOneWidget);
    expect(find.text('一句话智能填写'), findsNothing);
    await tester.tap(find.text('取消'));
    await tester.pumpAndSettle();
    expect(find.text('年度净收益'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('少量交易也可以进入筛选页并打开真实详情', (tester) async {
    await pumpPage(tester, BillingScreen(repository: dependencies.billing));
    await tester.tap(find.text('查看全部'));
    await tester.pumpAndSettle();
    expect(find.text('账单'), findsOneWidget);
    await tester.tap(find.text('肥料').first);
    await tester.pumpAndSettle();
    expect(find.text('复制金额'), findsOneWidget);
    expect(find.text('删除'), findsNothing);
    await tester.tap(find.text('关闭'));
    await tester.pumpAndSettle();
    expect(find.text('复制金额'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('账本失败后可发起重试', (tester) async {
    final adapter = RecordingAdapter({
      '/cost-records': paginatedCostsResponse,
      '/cost-records/summary/yearly': yearlySummaryResponse,
      '/debts': debtsResponse
    }, statusCodes: {
      '/cost-records': 500
    });
    final dio = Dio()..httpClientAdapter = adapter;
    await pumpPage(tester,
        BillingScreen(repository: BillingRepository(ApiClient(dio: dio))));
    expect(find.text('账本暂时无法加载'), findsOneWidget);
    // 错误状态保留重试入口，验证第二次请求确实发生。
    expect(find.text('重新加载'), findsOneWidget);
    await tester.tap(find.text('重新加载'));
    await tester.pumpAndSettle();
    expect(adapter.requests.where((request) => request.path == '/cost-records'),
        hasLength(2));
  });

  testWidgets('个人资料失败时保留页面标题与重试入口', (tester) async {
    final adapter = RecordingAdapter({}, statusCodes: {'/users/me': 500});
    final dio = Dio()..httpClientAdapter = adapter;
    await pumpPage(tester,
        ProfileScreen(repository: ProfileRepository(ApiClient(dio: dio))));
    expect(find.text('我的'), findsOneWidget);
    expect(find.text('重新加载'), findsOneWidget);
    await tester.tap(find.text('重新加载'));
    await tester.pumpAndSettle();
    expect(adapter.requests.where((request) => request.path == '/users/me'),
        hasLength(2));
  });

  testWidgets('技能搜索跨分类过滤并展示空结果', (tester) async {
    await pumpPage(tester, YayaSkillsPage(repository: dependencies.yaya));
    await tester.enterText(find.byType(TextField), '成本');
    await tester.pumpAndSettle();
    expect(find.text('成本分析'), findsOneWidget);
    expect(find.text('智能记账'), findsNothing);
    await tester.tap(find.byTooltip('查看成本分析详情'));
    await tester.pumpAndSettle();
    expect(find.text('可以这样问'), findsOneWidget);
    expect(tester.takeException(), isNull);
    Navigator.of(tester.element(find.text('可以这样问'))).pop();
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '不存在的技能');
    await tester.pumpAndSettle();
    expect(find.textContaining('没有匹配的技能'), findsOneWidget);
  });

  testWidgets('茬口搜索和状态筛选会实际过滤列表', (tester) async {
    final adapter = RecordingAdapter({
      '/crop-cycles': {
        'items': [
          cycleResponse,
          {...cycleResponse, 'id': 8, 'name': '秋季玉米', 'status': 'planned'}
        ],
        'total': 2
      }
    });
    final dio = Dio()..httpClientAdapter = adapter;
    await pumpPage(tester,
        FarmCycleListPage(repository: BusinessRepository(ApiClient(dio: dio))));
    await tester.enterText(find.byType(TextField), '秋季');
    await tester.pumpAndSettle();
    expect(find.text('秋季玉米'), findsOneWidget);
    expect(find.text(cycleResponse['name'] as String), findsNothing);
    await tester.enterText(find.byType(TextField), '');
    await tester.tap(find.text('计划').first);
    await tester.pumpAndSettle();
    expect(find.text('秋季玉米'), findsOneWidget);
    expect(find.text(cycleResponse['name'] as String), findsNothing);
  });

  testWidgets('回答风格弹窗窄屏大字体下能选择与关闭', (tester) async {
    await pumpPage(tester, ProfileScreen(repository: dependencies.profile),
        width: 320, scale: 1.3);
    await tester.ensureVisible(find.text('回答风格'));
    await tester.tap(find.text('回答风格'));
    await tester.pumpAndSettle();
    expect(find.text('冷静专业型'), findsOneWidget);
    await tester.tap(find.text('冷静专业型'));
    await tester.pumpAndSettle();
    expect(find.text('冷静专业型'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('真实交易数据可用于全部交易页', (tester) async {
    final model = await tester.runAsync(
        () => BillingController(repository: dependencies.billing).load());
    await pumpPage(tester, AllTransactionsScreen(model: model!),
        width: 320, scale: 1.3);
    expect(find.text('账单'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
  testWidgets('地区选择弹窗窄屏大字体下可定位与返回', (tester) async {
    await pumpPage(
        tester,
        ProfileScreen(
          repository: dependencies.profile,
          locations: dependencies.locations,
          location: dependencies.location,
        ),
        width: 320,
        scale: 1.3);
    await tester.tap(find.text('经营地区'));
    await tester.pumpAndSettle();
    expect(find.text('重新定位'), findsOneWidget);
    expect(tester.takeException(), isNull);
    Navigator.of(tester.element(find.text('重新定位'))).pop();
    await tester.pumpAndSettle();
    expect(find.text('经营地区'), findsOneWidget);
  });

  testWidgets('芽芽历史侧栏窄屏大字体下可打开与关闭', (tester) async {
    await pumpPage(
        tester, AppShell(dependencies: dependencies, initialIndex: 2),
        width: 320, scale: 1.3);
    await tester.tap(find.byIcon(LucideIcons.menu).first);
    await tester.pumpAndSettle();
    expect(find.text('农场助手'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.tap(find.byIcon(LucideIcons.menu).last);
    await tester.pumpAndSettle();
    expect(find.text('农场助手'), findsNothing);
  });
  testWidgets('芽芽键盘弹出后输入区与发送按钮仍可见', (tester) async {
    await pumpPage(
        tester, AppShell(dependencies: dependencies, initialIndex: 2));
    tester.view.viewInsets = const FakeViewPadding(bottom: 300);
    addTearDown(tester.view.resetViewInsets);
    await tester.tap(find.byType(TextField));
    await tester.pumpAndSettle();
    final field = tester.getRect(find.byType(TextField));
    final send = tester.getRect(find.byTooltip('发送'));
    expect(field.bottom, lessThanOrEqualTo(544));
    expect(send.bottom, lessThanOrEqualTo(544));
    expect(tester.takeException(), isNull);
    await tester.enterText(find.byType(TextField), '今天的农场记录\n需要补充说明');
    await tester.pumpAndSettle();
    expect(tester.widget<TextField>(find.byType(TextField)).maxLines, 4);
    expect(tester.takeException(), isNull);
  });
}
