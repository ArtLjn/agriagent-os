import 'package:farm_manager_app/features/yaya/yaya_screen.dart';
import 'package:farm_manager_app/theme/app_colors.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('聊天助手统一叫芽芽', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: YayaScreen()));

    expect(find.text('芽芽'), findsOneWidget);
    expect(find.text('AI 助手'), findsNothing);
    expect(find.textContaining('AI 会'), findsNothing);
    expect(find.text('芽芽会读取你的经营上下文'), findsOneWidget);
  });

  testWidgets('芽芽页面包含菜单、建议、聊天和输入框', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: YayaScreen()));

    expect(find.text('上下文：批次、作业、账单、天气'), findsOneWidget);
    expect(find.text('今天可以这样问'), findsOneWidget);
    expect(find.text('安排今天作业'), findsOneWidget);
    expect(find.text('分析成本'), findsOneWidget);
    expect(find.text('生成周报'), findsOneWidget);
    expect(find.text('输入问题或直接说“帮我安排今天”'), findsOneWidget);
  });

  test('芽芽主色不是紫色', () {
    expect(AppColors.teal.toARGB32(), isNot(0xFF8559F6));
  });
}
