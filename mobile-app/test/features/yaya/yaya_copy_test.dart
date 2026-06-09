import 'package:farm_manager_app/features/yaya/yaya_screen.dart';
import 'package:farm_manager_app/shared/assets/app_assets.dart';
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

  testWidgets('芽芽首页是轻量聊天助手布局', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: YayaScreen()));

    expect(find.byIcon(LucideIcons.menu), findsOneWidget);
    expect(find.byIcon(LucideIcons.volume2), findsOneWidget);
    expect(find.byIcon(LucideIcons.plus), findsWidgets);
    expect(find.text('今日简报'), findsNothing);
    expect(find.text('待确认'), findsNothing);
    expect(find.text('风险'), findsNothing);
    expect(find.text('今日待办'), findsNothing);
    expect(find.text('今天适合干什么'), findsWidgets);
    expect(find.text('本月成本怎么看'), findsOneWidget);
    expect(find.text('生成周报'), findsOneWidget);
    expect(find.text('深度思考'), findsOneWidget);
    expect(find.text('经营分析'), findsOneWidget);
    expect(find.text('生成报告'), findsOneWidget);
    expect(find.text('全部技能'), findsOneWidget);
    expect(find.text('发消息或按住说话...'), findsOneWidget);
  });

  testWidgets('点击菜单打开历史聊天抽屉', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: YayaScreen()));

    await tester.tap(find.byIcon(LucideIcons.menu));
    await tester.pumpAndSettle();

    expect(find.text('新对话'), findsOneWidget);
    expect(find.text('最近对话'), findsOneWidget);
    expect(find.text('7天内'), findsOneWidget);
    expect(find.text('张三'), findsOneWidget);
  });

  testWidgets('全部技能页使用独立 banner 图片资产', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: YayaSkillsPage()));

    expect(find.text('全部技能'), findsOneWidget);
    expect(find.text('搜索技能'), findsOneWidget);
    expect(find.byKey(const ValueKey('yaya-skills-banner')), findsOneWidget);
    final banner = tester.widget<Image>(
      find.byKey(const ValueKey('yaya-skills-banner')),
    );
    expect((banner.image as AssetImage).assetName, AppAssets.yayaSkillsBanner);
    expect(find.text('今日简报'), findsOneWidget);
    expect(find.text('智能记账'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('天气提醒'),
      240,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('天气提醒'), findsOneWidget);
  });

  test('芽芽主色不是紫色', () {
    expect(AppColors.teal.toARGB32(), isNot(0xFF8559F6));
  });
}
