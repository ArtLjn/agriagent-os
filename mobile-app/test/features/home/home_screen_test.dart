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
    expect(find.text('傍晚少量浇水'), findsOneWidget);
    expect(find.text('天气'), findsOneWidget);
    expect(find.text('晴'), findsOneWidget);
    expect(find.text('作业'), findsWidgets);
    expect(find.text('待处理'), findsOneWidget);
    expect(find.textContaining('寿光'), findsNothing);
    expect(find.text('1项'), findsWidgets);
    expect(find.text('资金概览'), findsOneWidget);
    expect(find.text('成本分析'), findsOneWidget);
    expect(find.text('茬口进度'), findsOneWidget);
    expect(find.text('风险预警'), findsOneWidget);
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
    expect(find.text('浇水'), findsWidgets);
    expect(find.text('AI 判断依据'), findsOneWidget);
    expect(find.text('执行步骤'), findsOneWidget);
    expect(find.text('关联事项'), findsOneWidget);
    expect(find.text('生成作业单'), findsOneWidget);
    expect(find.text('问问芽芽'), findsOneWidget);
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

    expect(fake.adapter.requests, hasLength(5));

    await tester.tap(find.text('刷新0'));
    await tester.pumpAndSettle();

    expect(fake.adapter.requests, hasLength(5));
  });
}

DashboardRepository _repository() {
  return _FakeHomeApi().repository;
}

class _FakeHomeApi {
  _FakeHomeApi()
      : adapter = RecordingAdapter({
          '/agent/daily': dailyAdviceResponse,
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
