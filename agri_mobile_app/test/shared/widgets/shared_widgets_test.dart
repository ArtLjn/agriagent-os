import 'package:farm_manager_app/shared/widgets/app_icon_tile.dart';
import 'package:farm_manager_app/shared/widgets/card_panel.dart';
import 'package:farm_manager_app/shared/widgets/chip_label.dart';
import 'package:farm_manager_app/theme/app_colors.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

void main() {
  testWidgets('CardPanel 使用克制圆角和边框', (tester) async {
    await tester
        .pumpWidget(const MaterialApp(home: CardPanel(child: Text('卡片'))));
    final decorated =
        tester.widget<DecoratedBox>(find.byType(DecoratedBox).first);
    final decoration = decorated.decoration as BoxDecoration;
    expect(decoration.borderRadius, BorderRadius.circular(16));
    expect(decoration.color, AppColors.surface);
  });

  testWidgets('AppIconTile 显示图标和标题', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: AppIconTile(icon: LucideIcons.bot, label: '芽芽')),
    );
    expect(find.text('芽芽'), findsOneWidget);
  });

  testWidgets('ChipLabel 显示短标签', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ChipLabel.blue('芽芽今日汇总')));
    expect(find.text('芽芽今日汇总'), findsOneWidget);
  });
}
