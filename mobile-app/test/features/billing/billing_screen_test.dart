import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/features/billing/billing_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  testWidgets('账本展示真实资金、交易、提醒和手动记账', (tester) async {
    await tester.pumpWidget(
        MaterialApp(home: BillingScreen(repository: _repository())));
    await tester.pumpAndSettle();

    expect(find.text('农场管家'), findsOneWidget);
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

  testWidgets('账本大金额交易可以渲染', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
          home: BillingScreen(repository: _repository(amount: '1234567890'))),
    );
    await tester.pumpAndSettle();

    expect(find.text('-¥1234567890'), findsOneWidget);
  });
}

BillingRepository _repository({String amount = '200'}) {
  return _FakeBillingApi(amount: amount).repository;
}

class _FakeBillingApi {
  _FakeBillingApi({String amount = '200'})
      : adapter = RecordingAdapter({
          '/costs': {
            'items': [
              {...costRecordResponse, 'amount': amount}
            ],
            'total': 1,
          },
          '/costs/summary/2026': yearlySummaryResponse,
          '/debts': debtsResponse,
        }) {
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    repository = BillingRepository(ApiClient(dio: dio));
  }

  final RecordingAdapter adapter;
  late final BillingRepository repository;
}
