import 'package:farm_manager_app/features/yaya/yaya_screen.dart';
import 'package:farm_manager_app/theme/app_colors.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

void main() {
  testWidgets('聊天助手统一叫芽芽', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: YayaScreen()));

    expect(find.textContaining('芽芽'), findsWidgets);
    expect(find.textContaining('AI 会'), findsNothing);
    expect(find.textContaining('我是芽芽'), findsOneWidget);
  });

  testWidgets('芽芽页面包含历史入口、简报、建议、模式和输入栏', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: YayaScreen()));

    expect(find.byIcon(LucideIcons.menu), findsOneWidget);
    expect(find.byIcon(LucideIcons.volume2), findsOneWidget);
    expect(find.byIcon(LucideIcons.plus), findsWidgets);
    expect(find.text('今日简报'), findsOneWidget);
    expect(find.text('今天适合干什么'), findsWidgets);
    expect(find.text('本月成本怎么看'), findsOneWidget);
    expect(find.text('深度思考'), findsOneWidget);
    expect(find.text('经营分析'), findsOneWidget);
    expect(find.text('生成报告'), findsOneWidget);
    expect(find.text('全部技能'), findsOneWidget);
    expect(find.text('发消息或按住说话...'), findsOneWidget);
  });

  test('芽芽主色不是紫色', () {
    expect(AppColors.teal.toARGB32(), isNot(0xFF8559F6));
  });
}
