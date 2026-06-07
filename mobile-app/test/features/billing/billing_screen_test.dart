import 'package:farm_manager_app/features/billing/billing_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('账单展示经营收支核心模块', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: BillingScreen()));

    expect(find.text('账单'), findsOneWidget);
    expect(find.text('经营收支、人工、欠款的核心入口'), findsOneWidget);
    expect(find.text('本月净支出'), findsOneWidget);
    expect(find.text('¥18,426'), findsOneWidget);
    expect(find.text('记收入'), findsOneWidget);
    expect(find.text('智能记账'), findsOneWidget);
    expect(find.text('结人工'), findsOneWidget);
    expect(find.text('成本构成'), findsOneWidget);
    expect(find.text('最近流水'), findsOneWidget);
  });

  testWidgets('账单不展示 API 路径', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: BillingScreen()));
    expect(find.textContaining('/'), findsNothing);
  });
}
