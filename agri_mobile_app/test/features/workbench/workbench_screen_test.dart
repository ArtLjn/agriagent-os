import 'package:farm_manager_app/features/workbench/workbench_screen.dart';
import 'package:farm_manager_app/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_app_dependencies.dart';

void main() {
  late FakeAppDependencies dependencies;
  setUp(() => dependencies = FakeAppDependencies());

  Future<void> pump(WidgetTester tester,
      {VoidCallback? onGoLedger,
      VoidCallback? onGoYaya,
      VoidCallback? onLedgerSaved,
      double width = 390}) async {
    tester.view.physicalSize = Size(width, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
        theme: AppTheme.light(),
        home: WorkbenchScreen(
          businessRepository: dependencies.business,
          onGoLedger: onGoLedger,
          onGoYaya: onGoYaya,
          onLedgerSaved: onLedgerSaved,
        )));
    await tester.pumpAndSettle();
  }

  testWidgets('记录页展示真实经营入口与日期，不使用样例指标', (tester) async {
    await pump(tester);
    for (final label in ['手动记一笔', '记农事', '记工资', '农场资料', '建批次', '新增工人', '建模板']) {
      expect(find.text(label), findsOneWidget);
    }
    final today = DateTime.now();
    expect(find.textContaining('${today.month}月${today.day}日'), findsOneWidget);
    expect(find.text('今日概览'), findsNothing);
    expect(find.text('生成月报'), findsNothing);
    expect(find.text('识别'), findsNothing);
    expect(find.textContaining('/api/'), findsNothing);
  });

  testWidgets('记录页窄屏布局不溢出', (tester) async {
    await pump(tester, width: 320);
    expect(tester.takeException(), isNull);
  });

  testWidgets('芽芽整理入口进入聊天', (tester) async {
    var opened = false;
    await pump(tester, onGoYaya: () => opened = true);
    await tester.tap(find.text('让芽芽帮你整理'));
    await tester.pumpAndSettle();
    expect(opened, isTrue);
  });

  for (final entry in {
    '手动记一笔': '保存记录',
    '记农事': '保存农事',
    '记工资': '保存工资',
    '建批次': '茬口管理',
    '新增工人': '工人管理',
    '建模板': '作物模板'
  }.entries) {
    testWidgets('${entry.key}可进入实际业务页面并返回', (tester) async {
      await pump(tester);
      await tester.ensureVisible(find.text(entry.key));
      await tester.tap(find.text(entry.key));
      await tester.pumpAndSettle();
      expect(find.text(entry.value), findsWidgets);
      final context = tester.element(find.text(entry.value).first);
      Navigator.of(context).pop();
      await tester.pumpAndSettle();
      expect(find.text('农场资料'), findsOneWidget);
    });
  }

  testWidgets('最近记录入口切换到账本', (tester) async {
    var opened = false;
    await pump(tester, onGoLedger: () => opened = true);
    await tester.ensureVisible(find.text('查看最近记录'));
    await tester.tap(find.text('查看最近记录'));
    await tester.pumpAndSettle();
    expect(opened, isTrue);
  });

  testWidgets('手动记账保存后通知账本刷新', (tester) async {
    var notifications = 0;
    await pump(tester, onLedgerSaved: () => notifications += 1);
    await tester.tap(find.text('手动记一笔'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('ledger-category-dropdown-search')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('ledger-category-option-肥料')));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, '0.00'), '200');
    await tester.tap(find.text('保存记录'));
    await tester.pumpAndSettle();
    expect(find.text('保存记录成功'), findsOneWidget);
    expect(notifications, 1);
  });
}
