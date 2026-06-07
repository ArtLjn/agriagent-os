import 'package:farm_manager_app/features/shell/app_shell.dart';
import 'package:farm_manager_app/features/shell/bottom_tab_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('底部导航包含五个 Tab 且中间是芽芽', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: AppShell()));

    expect(find.text('首页'), findsOneWidget);
    expect(find.text('工作台'), findsOneWidget);
    expect(find.text('芽芽'), findsOneWidget);
    expect(find.text('账单'), findsOneWidget);
    expect(find.text('我的'), findsOneWidget);
    expect(find.text('AI'), findsNothing);
  });

  testWidgets('芽芽按钮不会贴到底部边缘', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 375,
            height: 812,
            child: Align(
              alignment: Alignment.bottomCenter,
              child: AppBottomTabBar(selectedIndex: 2, onChanged: _noop),
            ),
          ),
        ),
      ),
    );

    final bar = tester.getRect(find.byType(AppBottomTabBar));
    final yaya = tester.getRect(find.text('芽芽'));
    expect(yaya.bottom, lessThan(bar.bottom - 4));
  });
}

void _noop(int index) {}
