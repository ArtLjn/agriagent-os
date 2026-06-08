import 'package:farm_manager_app/features/home/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('首页展示 AI 数据驾驶舱、建议、洞察和行动入口', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: HomeScreen()));

    expect(find.text('农场管家'), findsOneWidget);
    expect(find.text('今日经营态势'), findsOneWidget);
    expect(find.text('AI分析'), findsOneWidget);
    expect(find.text('86'), findsOneWidget);
    expect(find.text('经营稳定，注意午后天气'), findsOneWidget);
    expect(find.text('AI 今日建议'), findsOneWidget);
    expect(find.text('午后避开露天作业'), findsOneWidget);
    expect(find.text('西瓜批次补充灌溉'), findsOneWidget);
    expect(find.text('本月饲料成本偏高'), findsOneWidget);
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
    await tester.pumpWidget(const MaterialApp(home: HomeScreen()));
    expect(find.textContaining('/'), findsNothing);
  });
}
