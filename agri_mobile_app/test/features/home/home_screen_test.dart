import 'dart:async';

import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/api/api_models.dart';
import 'package:farm_manager_app/data/repositories/dashboard_repository.dart';
import 'package:farm_manager_app/features/home/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  for (final entry in {
    '晴': LucideIcons.sun,
    '多云': LucideIcons.cloudSun,
    '阴': LucideIcons.cloud,
    '小雨': LucideIcons.cloudRain,
    '大雪': LucideIcons.cloudSnow,
    '雷暴': LucideIcons.cloudLightning,
    '雾': LucideIcons.cloudFog,
  }.entries) {
    testWidgets('欢迎卡显示气温区间和${entry.key}图标', (tester) async {
      final semantics = tester.ensureSemantics();
      await _pumpHome(
          tester,
          _FakeHomeApi(weather: {
            ...v2WeatherResponse,
            'daily': [
              {'desc': entry.key, 'min_c': 17.2, 'max_c': 32.1}
            ],
          }));
      expect(find.text('17～32℃'), findsOneWidget);
      expect(find.text('天气暂未更新'), findsNothing);
      final icon =
          tester.widget<Icon>(find.byKey(const ValueKey('home-weather-icon')));
      expect(icon.icon, entry.value);
      expect(find.bySemanticsLabel('${entry.key}，气温 17～32℃'), findsOneWidget);
      semantics.dispose();
    });
  }

  testWidgets('更新首页同时更新气温区间和天气图标', (tester) async {
    final fake = _FakeHomeApi(weather: v2WeatherResponse);
    await _pumpHome(tester, fake);
    expect(find.text('17～32℃'), findsOneWidget);
    fake.adapter.responses['/weather'] = {
      'current_temp': 18,
      'daily': [
        {'desc': '小雨', 'min_c': 15, 'max_c': 23}
      ],
    };
    await tester.tap(find.byTooltip('更新首页'));
    await tester.pumpAndSettle();
    expect(find.text('15～23℃'), findsOneWidget);
    expect(find.text('17～32℃'), findsNothing);
    expect(
        tester
            .widget<Icon>(find.byKey(const ValueKey('home-weather-icon')))
            .icon,
        LucideIcons.cloudRain);
  });

  testWidgets('首页优先展示常用入口和经营概览，移除重复装饰信息', (tester) async {
    await _pumpHome(tester, _FakeHomeApi());

    expect(find.text('打理好你的\n每一天'), findsOneWidget);
    expect(find.text('经营概览'), findsOneWidget);
    expect(find.text('作业安排'), findsOneWidget);
    expect(find.text('未结人工'), findsOneWidget);
    expect(find.text('¥200'), findsOneWidget);
    expect(find.text('芽芽建议'), findsOneWidget);
    expect(find.text('82分'), findsOneWidget);
    expect(find.text('记农事'), findsOneWidget);
    expect(find.text('看账本'), findsOneWidget);
    expect(find.text('问芽芽'), findsOneWidget);
    expect(find.text('建议健康度'), findsNothing);
    expect(find.text('风险预警'), findsNothing);
    expect(find.text('AI分析'), findsNothing);
    expect(find.text('生成报告'), findsNothing);
  });

  testWidgets('三个常用入口和概览卡片切到正确页面', (tester) async {
    final selected = <int>[];
    await _pumpHome(tester, _FakeHomeApi(), onTab: selected.add);

    for (final label in ['记农事', '看账本', '问芽芽', '查看作业记录', '查看资金账本']) {
      await tester.ensureVisible(find.text(label));
      await tester.tap(find.text(label));
      await tester.pump();
    }
    expect(selected, [1, 3, 2, 1, 3]);
  });

  testWidgets('没有真实建议时显示芽芽入口，不显示空评分或伪详情', (tester) async {
    final selected = <int>[];
    await _pumpHome(tester, _FakeHomeApi(withAdvice: false),
        onTab: selected.add);

    expect(find.text('--'), findsNothing);
    expect(find.text('暂无评分'), findsNothing);
    expect(find.textContaining('今天还没有经营建议'), findsOneWidget);
    await tester.ensureVisible(find.text('问问芽芽'));
    await tester.tap(find.text('问问芽芽'));
    await tester.pump();
    expect(selected, [2]);
    expect(find.text('建议详情'), findsNothing);
  });

  testWidgets('请求失败后可以重试，更新按钮会重新读取数据', (tester) async {
    final statuses = <String, int>{'/dashboard': 503};
    final fake = _FakeHomeApi(statusCodes: statuses);
    await _pumpHome(tester, fake);
    expect(find.text('暂时没能更新首页'), findsOneWidget);
    expect(find.text('重新加载'), findsOneWidget);

    statuses.clear();
    await tester.tap(find.text('重新加载'));
    await tester.pumpAndSettle();
    expect(find.text('经营概览'), findsOneWidget);
    expect(fake.adapter.requests, hasLength(8));

    await tester.tap(find.byTooltip('更新首页'));
    await tester.pumpAndSettle();
    expect(fake.adapter.requests, hasLength(12));
  });

  testWidgets('下拉刷新重新读取首页数据', (tester) async {
    final fake = _FakeHomeApi(withAdvice: false);
    await _pumpHome(tester, fake);
    await tester.drag(
        find.byType(SingleChildScrollView).first, const Offset(0, 400));
    await tester.pumpAndSettle();
    expect(fake.adapter.requests, hasLength(8));
  });

  testWidgets('后端等待期间常用入口仍可使用', (tester) async {
    final pending = Completer<Map<String, dynamic>>();
    final fake = _FakeHomeApi(overview: pending.future, withAdvice: false);
    final selected = <int>[];
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
      body: HomeScreen(
          repository: fake.repository, onBottomTabChanged: selected.add),
    )));
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('正在整理农场记录'), findsOneWidget);
    await tester.tap(find.text('记农事'));
    await tester.pump();
    expect(selected, [1]);
    pending.complete({'location': '苏州'});
    await tester.pumpAndSettle();
    expect(find.text('经营概览'), findsOneWidget);
  });

  for (final size in [const Size(320, 568), const Size(390, 844)]) {
    testWidgets('首页在 ${size.width.toInt()} 宽度和大字体下可滚动操作', (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await _pumpHome(tester, _FakeHomeApi(withAdvice: false), scale: 1.3);
      expect(tester.takeException(), isNull);
      await tester.ensureVisible(find.text('问问芽芽'));
      expect(tester.takeException(), isNull);
      expect(find.text('每一份耕耘，都值得被记住'), findsOneWidget);
    });
  }

  testWidgets('首页不展示 API 路径', (tester) async {
    await tester
        .pumpWidget(MaterialApp(home: HomeScreen(repository: _repository())));
    await tester.pumpAndSettle();
    expect(find.textContaining('/'), findsNothing);
  });

  testWidgets('点击今日建议进入详情页', (tester) async {
    await tester
        .pumpWidget(MaterialApp(home: HomeScreen(repository: _repository())));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('浇水'));
    await tester.tap(find.text('浇水'));
    await tester.pumpAndSettle();

    expect(find.text('建议详情'), findsOneWidget);
    expect(find.text('傍晚补水'), findsWidgets);
    expect(find.text('今天高温明显，建议傍晚少量补水并观察土壤墒情。'), findsOneWidget);
    expect(find.text('AI 判断依据'), findsOneWidget);
    expect(find.text('执行步骤'), findsOneWidget);
    expect(find.text('关联事项'), findsOneWidget);
    expect(find.text('生成作业单'), findsNothing);
    expect(find.text('问问芽芽'), findsOneWidget);
  });

  testWidgets('详情页只展示接口返回的详情字段', (tester) async {
    final partialAdvice = Map<String, dynamic>.from(dailyAdviceResponse);
    partialAdvice['items'] = [
      {
        'id': 'operation:work_order:1',
        'category': 'operation',
        'level': 'urgent',
        'source_type': 'operation_work_order',
        'source_id': 1,
        'title': '补做定植作业',
        'detail': '定植和浇水作业已逾期9天，请尽快安排人员补做。',
        'priority': 1,
        'icon': 'ClipboardList',
        'compact': {
          'title': '补做定植作业',
          'subtitle': '定植和浇水作业已逾期9天，请尽快安排人员补做。',
          'icon': 'ClipboardList',
          'icon_color': 'blue',
        },
        'detail_view': {
          'title': '逾期作业补上',
          'description': '定植和浇水作业已逾期9天，请尽快安排人员补做。',
          'actions': [
            {
              'type': 'create_work_order',
              'label': '生成作业单',
              'payload': {'candidate_id': 'operation:work_order:1'},
            },
          ],
        },
      }
    ];
    final fake = _FakeHomeApi(dailyAdvice: partialAdvice);

    await tester
        .pumpWidget(MaterialApp(home: HomeScreen(repository: fake.repository)));
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('补做定植作业'));
    await tester.tap(find.text('补做定植作业'));
    await tester.pumpAndSettle();

    expect(find.text('逾期作业补上'), findsOneWidget);
    expect(find.text('AI 判断依据'), findsNothing);
    expect(find.text('执行步骤'), findsNothing);
    expect(find.text('关联事项'), findsNothing);
    expect(find.text('暂无更多判断依据'), findsNothing);
    expect(find.text('暂无关联事项'), findsNothing);
    expect(find.text('今日建议'), findsNothing);
    expect(find.text('生成作业单'), findsOneWidget);
    expect(find.text('问问芽芽'), findsNothing);
  });

  testWidgets('父级 rebuild 后首页不重复请求数据', (tester) async {
    final fake = _FakeHomeApi();
    var version = 0;

    await tester.pumpWidget(
      StatefulBuilder(
        builder: (context, setState) {
          return MaterialApp(
            home: Column(
              children: [
                TextButton(
                  onPressed: () => setState(() => version += 1),
                  child: Text('刷新$version'),
                ),
                Expanded(child: HomeScreen(repository: fake.repository)),
              ],
            ),
          );
        },
      ),
    );
    await tester.pumpAndSettle();

    expect(fake.adapter.requests, hasLength(4));

    await tester.tap(find.text('刷新0'));
    await tester.pumpAndSettle();

    expect(fake.adapter.requests, hasLength(4));
  });
}

DashboardRepository _repository() {
  return _FakeHomeApi().repository;
}

Future<void> _pumpHome(WidgetTester tester, _FakeHomeApi fake,
    {ValueChanged<int>? onTab, double scale = 1}) async {
  await tester.pumpWidget(MaterialApp(
    home: MediaQuery(
      data: MediaQueryData(textScaler: TextScaler.linear(scale)),
      child: Scaffold(
          body: HomeScreen(
              repository: fake.repository, onBottomTabChanged: onTab)),
    ),
  ));
  await tester.pumpAndSettle();
}

class _FakeHomeApi {
  _FakeHomeApi(
      {Map<String, dynamic>? dailyAdvice,
      bool withAdvice = true,
      Object? overview,
      Map<String, dynamic>? weather,
      Map<String, int> statusCodes = const {}})
      : adapter = RecordingAdapter({
          '/dashboard': overview ?? {'location': '苏州', 'active_cycles': []},
          '/weather': weather ?? weatherResponse,
          '/work-orders': paginatedWorkOrdersResponse,
          '/labor/unsettled-summary': unsettledLaborSummaryResponse,
        }, statusCodes: statusCodes) {
    final dio = Dio(BaseOptions(baseUrl: 'http://10.0.2.2:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    repository = _HomeTestRepository(ApiClient(dio: dio),
        advice: withAdvice
            ? DailyAdvice.fromJson(dailyAdvice ?? dailyAdviceResponse)
            : null);
  }

  final RecordingAdapter adapter;
  late final DashboardRepository repository;
}

class _HomeTestRepository extends DashboardRepository {
  _HomeTestRepository(super.client, {this.advice});

  final DailyAdvice? advice;

  @override
  Future<DailyAdvice> getDailyAdvice({int? cycleId}) async {
    final overview = await super.getDailyAdvice(cycleId: cycleId);
    return advice ?? overview;
  }
}
