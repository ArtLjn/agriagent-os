import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/dashboard_repository.dart';
import 'package:farm_manager_app/features/home/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  testWidgets('首页展示真实建议、天气、作业和人工摘要，同时保留模块入口', (tester) async {
    await tester
        .pumpWidget(MaterialApp(home: HomeScreen(repository: _repository())));
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel('田掌柜'), findsOneWidget);
    expect(find.text('今日经营态势'), findsOneWidget);
    expect(find.text('AI分析'), findsOneWidget);
    expect(find.text('AI 今日建议'), findsOneWidget);
    expect(find.text('注意控水'), findsOneWidget);
    expect(find.text('浇水'), findsOneWidget);
    expect(find.text('傍晚少量浇水，避开中午高温时段。'), findsOneWidget);
    expect(find.text('天气'), findsOneWidget);
    expect(find.text('晴'), findsOneWidget);
    expect(find.text('作业'), findsWidgets);
    expect(find.text('待处理'), findsOneWidget);
    expect(find.textContaining('寿光'), findsNothing);
    expect(find.text('1项'), findsWidgets);
    expect(find.text('资金概览'), findsOneWidget);
    expect(find.text('作业跟进'), findsOneWidget);
    expect(find.text('建议健康度'), findsOneWidget);
    expect(find.text('82分'), findsOneWidget);
    expect(find.text('风险预警'), findsOneWidget);
    expect(find.text('1项待处理'), findsOneWidget);
    expect(find.text('茬口进度'), findsNothing);
    expect(find.text('8%'), findsNothing);
    expect(find.text('问问芽芽'), findsOneWidget);
    expect(find.text('记一笔'), findsOneWidget);
    expect(find.text('生成报告'), findsOneWidget);
    expect(find.text('今日待办'), findsNothing);
    expect(find.text('最近记录'), findsNothing);
  });

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

class _FakeHomeApi {
  _FakeHomeApi({Map<String, dynamic>? dailyAdvice})
      : adapter = RecordingAdapter({
          '/agent/daily': dailyAdvice ?? dailyAdviceResponse,
          '/settings': settingsResponse,
          '/weather/forecast': weatherResponse,
          '/planting/work-orders': paginatedWorkOrdersResponse,
          '/planting/labor/unsettled-summary': unsettledLaborSummaryResponse,
        }) {
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    repository = DashboardRepository(ApiClient(dio: dio));
  }

  final RecordingAdapter adapter;
  late final DashboardRepository repository;
}
