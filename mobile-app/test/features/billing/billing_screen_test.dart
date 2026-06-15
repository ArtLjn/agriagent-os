import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/features/billing/billing_controller.dart';
import 'package:farm_manager_app/features/billing/billing_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  testWidgets('账本展示真实资金、交易、提醒和手动记账', (tester) async {
    await tester.pumpWidget(
        MaterialApp(home: BillingScreen(repository: _repository())));
    await tester.pumpAndSettle();

    expect(find.bySemanticsLabel('田掌柜'), findsOneWidget);
    expect(find.text('资金概览'), findsOneWidget);
    expect(find.text('AI财务洞察'), findsOneWidget);
    expect(find.text('收入'), findsOneWidget);
    expect(find.text('支出'), findsOneWidget);
    expect(find.text('欠款'), findsOneWidget);
    expect(find.text('¥0'), findsOneWidget);
    expect(find.text('¥200'), findsWidgets);
    expect(find.text('-¥200'), findsWidgets);
    expect(find.text('最近交易'), findsOneWidget);
    expect(find.text('肥料'), findsOneWidget);
    expect(find.textContaining('老王'), findsWidgets);
    expect(find.text('待收款提醒'), findsOneWidget);
    expect(find.text('手动记一笔'), findsOneWidget);
    expect(find.text('AI帮我填'), findsNothing);
    expect(find.text('AI待确认'), findsNothing);
    expect(find.text('智能记账'), findsNothing);
  });

  testWidgets('账本不展示 API 路径', (tester) async {
    await tester.pumpWidget(
        MaterialApp(home: BillingScreen(repository: _repository())));
    await tester.pumpAndSettle();
    expect(find.textContaining('/api'), findsNothing);
  });

  testWidgets('父级 rebuild 后账本不重复请求数据', (tester) async {
    final fake = _FakeBillingApi();
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
                Expanded(child: BillingScreen(repository: fake.repository)),
              ],
            ),
          );
        },
      ),
    );
    await tester.pumpAndSettle();

    expect(fake.adapter.requests, hasLength(3));

    await tester.tap(find.text('刷新0'));
    await tester.pumpAndSettle();

    expect(fake.adapter.requests, hasLength(3));
  });

  testWidgets('账本 refreshKey 变化后重新请求数据', (tester) async {
    final fake = _FakeBillingApi();
    var refreshKey = 0;

    await tester.pumpWidget(
      StatefulBuilder(
        builder: (context, setState) {
          return MaterialApp(
            home: Column(
              children: [
                TextButton(
                  onPressed: () => setState(() => refreshKey += 1),
                  child: const Text('刷新账本'),
                ),
                Expanded(
                  child: BillingScreen(
                    repository: fake.repository,
                    refreshKey: refreshKey,
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
    await tester.pumpAndSettle();

    expect(fake.adapter.requests, hasLength(3));

    await tester.tap(find.text('刷新账本'));
    await tester.pumpAndSettle();

    expect(fake.adapter.requests, hasLength(6));
  });

  testWidgets('账本大金额交易可以渲染', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
          home: BillingScreen(repository: _repository(amount: '1234567890'))),
    );
    await tester.pumpAndSettle();

    expect(find.text('-¥1234567890'), findsOneWidget);
  });

  testWidgets('账本年度净收益大金额紧凑展示', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: BillingScreen(
          repository: _repository(summary: {
            ...yearlySummaryResponse,
            'net_profit': '-110970.16',
          }),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('-¥11.1万'), findsOneWidget);
  });

  testWidgets('账本概览小指标大金额紧凑展示', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: BillingScreen(
          repository: _repository(summary: {
            ...yearlySummaryResponse,
            'total_income': '5500',
            'total_cost': '116470.16',
            'net_profit': '-110970.16',
          }),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('¥11.6万'), findsOneWidget);
    expect(find.text('¥116470.16'), findsNothing);
  });

  testWidgets('账本洞察为空时使用兜底文案', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: AiFinanceInsightCard(
            model: BillingViewModel(
              incomeText: '¥0',
              expenseText: '¥0',
              netProfitText: '¥0',
              debtText: '¥0',
              transactions: [],
              receivables: [],
            ),
          ),
        ),
      ),
    );

    expect(find.text('AI财务洞察'), findsOneWidget);
    expect(find.textContaining('已读取本年收支数据'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('账本首页预览最近交易并可进入全部交易页', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: BillingScreen(
          repository: _repository(costs: _manyCostsResponse()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('最近交易'), findsOneWidget);
    expect(find.text('查看全部'), findsOneWidget);
    expect(find.text('交易6'), findsNothing);

    await tester.tap(find.text('查看全部'));
    await tester.pumpAndSettle();

    expect(find.text('全部交易'), findsOneWidget);
    expect(find.text('2026年6月'), findsOneWidget);
    expect(find.text('全部'), findsOneWidget);
    expect(find.text('交易6'), findsOneWidget);
  });

  testWidgets('全部交易页交易卡片使用内部滚动列表', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: BillingScreen(
          repository: _repository(costs: _manyCostsResponse(count: 12)),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('查看全部'));
    await tester.pumpAndSettle();

    expect(find.byType(Scrollbar), findsOneWidget);
    expect(find.byType(ListView), findsOneWidget);
    expect(find.text('交易12'), findsNothing);

    for (var i = 0; i < 4; i++) {
      await tester.drag(find.byType(ListView), const Offset(0, -300));
      await tester.pumpAndSettle();
    }

    expect(find.text('交易12'), findsOneWidget);
  });

  testWidgets('全部交易页 tab 切换会过滤交易', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: BillingScreen(
          repository: _repository(costs: _mixedCostsResponse()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('查看全部'));
    await tester.pumpAndSettle();

    expect(find.text('支出交易'), findsOneWidget);
    expect(find.text('收入交易'), findsOneWidget);
    expect(find.text('欠款交易'), findsOneWidget);

    await tester.tap(find.byKey(const Key('transaction-filter-income')));
    await tester.pumpAndSettle();

    expect(find.text('收入交易'), findsOneWidget);
    expect(find.text('支出交易'), findsNothing);
    expect(find.text('欠款交易'), findsNothing);

    await tester.tap(find.byKey(const Key('transaction-filter-debt')));
    await tester.pumpAndSettle();

    expect(find.text('欠款交易'), findsOneWidget);
    expect(find.text('收入交易'), findsNothing);
  });

  testWidgets('全部交易页日期筛选会切换月份范围', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: BillingScreen(
          repository: _repository(costs: _mixedCostsResponse()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('查看全部'));
    await tester.pumpAndSettle();
    expect(find.text('支出交易'), findsOneWidget);
    expect(find.text('上月交易'), findsNothing);

    await tester.tap(find.byKey(const Key('transaction-date-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('上月'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('确认'));
    await tester.pumpAndSettle();

    expect(find.text('2026年5月'), findsOneWidget);
    expect(find.text('上月交易'), findsOneWidget);
    expect(find.text('支出交易'), findsNothing);

    await tester.tap(find.byKey(const Key('transaction-date-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('全部时间'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('确认'));
    await tester.pumpAndSettle();

    expect(find.text('全部时间'), findsWidgets);
    expect(find.text('支出交易'), findsOneWidget);
    expect(find.text('上月交易'), findsOneWidget);
  });

  testWidgets('全部交易页日历翻月后确认会应用该月份', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: BillingScreen(
          repository: _repository(costs: _mixedCostsResponse()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('查看全部'));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('transaction-date-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('date-filter-prev-month')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('date-filter-confirm')));
    await tester.pumpAndSettle();

    expect(find.text('2026年5月'), findsOneWidget);
    expect(find.text('上月交易'), findsOneWidget);
    expect(find.text('支出交易'), findsNothing);
  });
}

BillingRepository _repository({
  String amount = '200',
  Map<String, dynamic>? summary,
  Map<String, dynamic>? costs,
}) {
  return _FakeBillingApi(amount: amount, summary: summary, costs: costs)
      .repository;
}

class _FakeBillingApi {
  _FakeBillingApi({
    String amount = '200',
    Map<String, dynamic>? summary,
    Map<String, dynamic>? costs,
  }) : adapter = RecordingAdapter({
          '/costs': costs ??
              {
                'items': [
                  {...costRecordResponse, 'amount': amount}
                ],
                'total': 1,
              },
          '/costs/summary/2026': summary ?? yearlySummaryResponse,
          '/debts': debtsResponse,
        }) {
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    repository = BillingRepository(ApiClient(dio: dio));
  }

  final RecordingAdapter adapter;
  late final BillingRepository repository;
}

Map<String, dynamic> _manyCostsResponse({int count = 6}) {
  return {
    'items': List.generate(count, (index) {
      final number = index + 1;
      final day = (10 - index).clamp(1, 28);
      return {
        ...costRecordResponse,
        'id': number,
        'category': '交易$number',
        'amount': '${number * 100}',
        'record_date': '2026-06-$day',
        'counterparty': null,
      };
    }),
    'total': count,
  };
}

Map<String, dynamic> _mixedCostsResponse() {
  return {
    'items': [
      {
        ...costRecordResponse,
        'id': 1,
        'record_type': 'cost',
        'category': '支出交易',
        'amount': '100',
        'record_date': '2026-06-09',
        'counterparty': null,
      },
      {
        ...costRecordResponse,
        'id': 2,
        'record_type': 'income',
        'category': '收入交易',
        'amount': '500',
        'record_date': '2026-06-08',
        'counterparty': null,
      },
      {
        ...costRecordResponse,
        'id': 3,
        'record_type': 'debt',
        'category': '欠款交易',
        'amount': '300',
        'record_date': '2026-06-07',
        'counterparty': '张三',
      },
      {
        ...costRecordResponse,
        'id': 4,
        'record_type': 'cost',
        'category': '上月交易',
        'amount': '200',
        'record_date': '2026-05-20',
        'counterparty': null,
      },
      {
        ...costRecordResponse,
        'id': 5,
        'record_type': 'cost',
        'category': '交易5',
        'amount': '100',
        'record_date': '2026-06-06',
        'counterparty': null,
      },
      {
        ...costRecordResponse,
        'id': 6,
        'record_type': 'cost',
        'category': '交易6',
        'amount': '100',
        'record_date': '2026-06-05',
        'counterparty': null,
      },
    ],
    'total': 6,
  };
}
