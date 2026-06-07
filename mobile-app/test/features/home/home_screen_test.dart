import 'package:farm_manager_app/features/home/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('首页展示芽芽汇总、天气、待处理事项', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: HomeScreen()));

    expect(find.text('今日概览'), findsOneWidget);
    expect(find.text('芽芽汇总了天气、建议、作业和账单'), findsOneWidget);
    expect(find.text('芽芽今日汇总'), findsOneWidget);
    expect(find.text('今天先做东棚授粉复核，傍晚前处理降温风险。'), findsOneWidget);
    expect(find.text('24℃'), findsOneWidget);
    expect(find.text('8℃'), findsOneWidget);
    expect(find.text('良好'), findsOneWidget);
    expect(find.text('今天要处理'), findsOneWidget);
  });

  testWidgets('首页不展示 API 路径', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: HomeScreen()));
    expect(find.textContaining('/'), findsNothing);
  });
}
