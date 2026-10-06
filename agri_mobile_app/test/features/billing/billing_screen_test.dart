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

    expect(find.text('账本'), findsOneWidget);
    expect(find.text('年度净收益'), findsOneWidget);
    expect(find.text('经营提示'), findsOneWidget);
    expect(find.text('收入'), findsWidgets);
    expect(find.text('支出'), findsWidgets);
    expect(find.text('欠款'), findsWidgets);
    expect(find.text('¥0'), findsOneWidget);
    expect(find.text('¥200'), findsWidgets);
    expect(find.text('-¥200'), findsWidgets);
    expect(find.text('最近交易'), findsOneWidget);
    expect(find.text('肥料'), findsOneWidget);
    expect(find.text('AI帮我填'), findsNothing);
    expect(find.text('AI待确认'), findsNothing);
    expect(find.text('智能记账'), findsNothing);
  });

  testWidgets('账本首页按日期整理流水，点击可查看真实金额和备注', (tester) async {
    await tester.pumpWidget(MaterialApp(
        home: BillingScreen(
            repository: _repository(costs: _manyCostsResponse()))));
    await tester.pumpAndSettle();
    final first = find.text('交易1');
    final second = find.text('交易2');
    expect(tester.getTopLeft(first).dy, lessThan(tester.getTopLeft(second).dy));
    await tester.ensureVisible(first);
    await tester.tap(first);
    await tester.pumpAndSettle();
    expect(find.text('复制金额'), findsOneWidget);
    expect(find.text('备注'), findsOneWidget);
    expect(find.text('关闭'), findsOneWidget);
    await tester.tap(find.text('关闭'));
    await tester.pumpAndSettle();
    expect(find.text('复制金额'), findsNothing);
  });

  testWidgets('没有交易时显示记账引导，不显示装饰曲线与 AI 分析', (tester) async {
    await tester.pumpWidget(MaterialApp(
        home: BillingScreen(
            repository: _repository(costs: {'items': [], 'total': 0}))));
    await tester.pumpAndSettle();
    expect(find.text('暂无交易'), findsOneWidget);
    expect(find.textContaining('从第一笔收支开始'), findsOneWidget);
    expect(find.text('AI 财务洞察'), findsNothing);
    expect(find.text('经营提示'), findsOneWidget);
    await tester.tap(find.text('查看全部'));
    await tester.pumpAndSettle();
    expect(find.text('账单'), findsOneWidget);
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

    expect(find.text('-¥1,234,567,890'), findsOneWidget);
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
          body: FinanceNoteCard(
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

    expect(find.text('经营提示'), findsOneWidget);
    expect(find.textContaining('让经营复盘有据可依'), findsOneWidget);
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

    expect(find.text('账单'), findsOneWidget);
    expect(find.textContaining(_monthTitle(0)), findsWidgets);
    expect(find.text('全部'), findsOneWidget);
    expect(find.text('交易6'), findsOneWidget);
  });

  testWidgets('账单详情页交易列表跟随整页滚动', (tester) async {
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

    expect(find.text('账单'), findsOneWidget);
    expect(find.text('新增记录'), findsNothing);
    expect(find.text('交易12'), findsOneWidget);

    for (var i = 0; i < 4; i++) {
      await tester.drag(
          find.byType(SingleChildScrollView), const Offset(0, -300));
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

    await tester.tap(find.text('收入').last);
    await tester.pumpAndSettle();

    expect(find.text('收入交易'), findsOneWidget);
    expect(find.text('支出交易'), findsNothing);
    expect(find.text('欠款交易'), findsNothing);

    await tester.tap(find.text('欠款').last);
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
    await tester.tap(find.text('应用筛选'));
    await tester.pumpAndSettle();

    expect(find.textContaining(_monthTitle(-1)), findsWidgets);
    expect(find.text('上月交易'), findsOneWidget);
    expect(find.text('支出交易'), findsNothing);

    await tester.tap(find.byKey(const Key('transaction-date-filter')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('全部时间'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('应用筛选'));
    await tester.pumpAndSettle();

    expect(find.textContaining('全部时间'), findsWidgets);
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

    expect(find.textContaining(_monthTitle(-1)), findsWidgets);
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
          '/cost-records': costs ??
              {
                'items': [
                  {...costRecordResponse, 'amount': amount}
                ],
                'total': 1,
              },
          '/cost-records/summary/yearly': summary ?? yearlySummaryResponse,
          '/debts': debtsResponse,
        }) {
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
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
        'record_date': _recordDate(0, day),
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
        'record_date': _recordDate(0, 9),
        'counterparty': null,
      },
      {
        ...costRecordResponse,
        'id': 2,
        'record_type': 'income',
        'category': '收入交易',
        'amount': '500',
        'record_date': _recordDate(0, 8),
        'counterparty': null,
      },
      {
        ...costRecordResponse,
        'id': 3,
        'record_type': 'debt',
        'category': '欠款交易',
        'amount': '300',
        'record_date': _recordDate(0, 7),
        'counterparty': '张三',
      },
      {
        ...costRecordResponse,
        'id': 4,
        'record_type': 'cost',
        'category': '上月交易',
        'amount': '200',
        'record_date': _recordDate(-1, 20),
        'counterparty': null,
      },
      {
        ...costRecordResponse,
        'id': 5,
        'record_type': 'cost',
        'category': '交易5',
        'amount': '100',
        'record_date': _recordDate(0, 6),
        'counterparty': null,
      },
      {
        ...costRecordResponse,
        'id': 6,
        'record_type': 'cost',
        'category': '交易6',
        'amount': '100',
        'record_date': _recordDate(0, 5),
        'counterparty': null,
      },
    ],
    'total': 6,
  };
}

String _monthTitle(int offset) {
  final now = DateTime.now();
  final month = DateTime(now.year, now.month + offset);
  return '${month.year}年${month.month}月';
}

String _recordDate(int offset, int day) {
  final now = DateTime.now();
  return DateTime(now.year, now.month + offset, day)
      .toIso8601String()
      .split('T')
      .first;
}
