import 'package:farm_manager_app/features/workbench/workbench_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('工作台展示平台功能入口', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: WorkbenchScreen()));

    expect(find.text('工作台'), findsOneWidget);
    expect(find.text('平台所有功能的快捷入口'), findsOneWidget);
    expect(find.text('常用功能'), findsOneWidget);
    expect(find.text('新建作业'), findsOneWidget);
    expect(find.text('种植批次'), findsOneWidget);
    expect(find.text('工人工资'), findsOneWidget);
    expect(find.text('快速记账'), findsOneWidget);
    expect(find.text('生产管理'), findsOneWidget);
    expect(find.text('进行中的批次'), findsOneWidget);
  });

  testWidgets('工作台不展示 API 路径', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: WorkbenchScreen()));
    expect(find.textContaining('/'), findsNothing);
  });
}
