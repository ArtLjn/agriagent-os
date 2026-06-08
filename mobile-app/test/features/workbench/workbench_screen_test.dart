import 'package:farm_manager_app/features/workbench/workbench_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('记录页展示 AI 帮填、手动快捷记录和确认卡', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: WorkbenchScreen()));

    expect(find.text('农场管家'), findsOneWidget);
    expect(find.text('AI帮我填'), findsOneWidget);
    expect(find.text('自己填'), findsOneWidget);
    expect(find.text('例如：今天买饲料 3680 元'), findsOneWidget);
    expect(find.text('手动快捷记录'), findsOneWidget);
    expect(find.text('记账'), findsOneWidget);
    expect(find.text('建模板'), findsOneWidget);
    expect(find.text('AI待确认'), findsOneWidget);
    expect(find.text('改一下'), findsOneWidget);
    expect(find.text('保存'), findsOneWidget);
  });

  testWidgets('工作台不展示 API 路径', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: WorkbenchScreen()));
    expect(find.textContaining('/'), findsNothing);
  });
}
