import 'package:farm_manager_app/features/shell/bottom_tab_bar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('底部导航包含五个 Tab 且中间是芽芽', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: AppBottomTabBar(selectedIndex: 0, onChanged: _noop),
        ),
      ),
    );

    expect(find.text('首页'), findsOneWidget);
    expect(find.text('记录'), findsOneWidget);
    expect(find.text('芽芽'), findsOneWidget);
    expect(find.text('账本'), findsOneWidget);
    expect(find.text('我的'), findsOneWidget);
    expect(find.text('AI'), findsNothing);
  });

  testWidgets('选中标记在导航之间连续移动，快速改选会落在最终目标', (tester) async {
    var selected = 0;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: Align(
      alignment: Alignment.bottomCenter,
      child: StatefulBuilder(
          builder: (context, update) => AppBottomTabBar(
              selectedIndex: selected,
              onChanged: (index) => update(() => selected = index))),
    ))));
    await tester.pumpAndSettle();
    final indicator = find.byKey(const ValueKey('tab-active-indicator'));
    final start = tester.getRect(indicator).left;
    await tester.tap(find.text('账本'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 60));
    final during = tester.getRect(indicator).left;
    await tester.pumpAndSettle();
    final end = tester.getRect(indicator).left;
    expect(during, greaterThan(start));
    expect(during, lessThan(end));
    await tester.tap(find.text('我的'));
    await tester.pump(const Duration(milliseconds: 40));
    await tester.tap(find.text('记录'));
    await tester.pumpAndSettle();
    expect(selected, 1);
    expect(tester.getRect(indicator).left, lessThan(end));
    expect(tester.takeException(), isNull);
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
