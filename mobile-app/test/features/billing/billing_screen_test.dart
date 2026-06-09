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
}

BillingRepository _repository() {
  final adapter = RecordingAdapter({
    '/costs': paginatedCostsResponse,
    '/costs/summary/2026': yearlySummaryResponse,
    '/debts': debtsResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
  dio.httpClientAdapter = adapter;
  return BillingRepository(ApiClient(dio: dio));
}
