import 'package:farm_manager_app/features/billing/billing_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('账本展示资金、交易、提醒和手动记账', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: BillingScreen()));

    expect(find.text('农场管家'), findsOneWidget);
    expect(find.text('资金概览'), findsOneWidget);
    expect(find.text('AI财务洞察'), findsOneWidget);
    expect(find.text('收入(元)'), findsOneWidget);
    expect(find.text('最近交易'), findsOneWidget);
    expect(find.text('饲料采购'), findsOneWidget);
    expect(find.text('待收款提醒'), findsOneWidget);
    expect(find.text('手动记一笔'), findsOneWidget);
    expect(find.text('AI帮我填'), findsNothing);
    expect(find.text('AI待确认'), findsNothing);
    expect(find.text('智能记账'), findsNothing);
  });

  testWidgets('账本不展示 API 路径', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: BillingScreen()));
    expect(find.textContaining('/api'), findsNothing);
  });
}
