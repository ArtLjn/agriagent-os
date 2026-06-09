import 'package:farm_manager_app/features/record_flow/record_ai_confirm_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_manual_edit_screen.dart';
import 'package:farm_manager_app/features/record_flow/record_save_success_screen.dart';
import 'package:farm_manager_app/features/shell/app_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/fake_app_dependencies.dart';

void main() {
  Future<void> pumpFlow(WidgetTester tester, Widget child) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(MaterialApp(home: child));
  }

  testWidgets('AI 解析确认页展示理解卡、原话和字段信息', (tester) async {
    await pumpFlow(tester, const RecordAiConfirmScreen());

    expect(find.text('智能确认'), findsOneWidget);
    expect(find.text('识别完成'), findsOneWidget);
    expect(find.text('确认保存'), findsWidgets);
    expect(find.text('我理解为'), findsOneWidget);
    expect(find.text('记一笔支出'), findsOneWidget);
    expect(find.text('¥3,680'), findsOneWidget);
    expect(find.text('用户原话  今天买饲料花了3680，记到5月第2批次'), findsOneWidget);
    expect(find.text('账务信息'), findsOneWidget);
    expect(find.text('关联信息'), findsOneWidget);
    expect(find.text('不确定？点字段可以修改'), findsOneWidget);
  });

  testWidgets('手动校正页展示分组卡片、切换项和保存入口', (tester) async {
    await pumpFlow(tester, const RecordManualEditScreen());

    expect(find.text('改一下'), findsOneWidget);
    expect(find.text('哪里不对，点哪里改'), findsOneWidget);
    expect(find.text('AI已帮你填好大部分'), findsOneWidget);
    expect(find.text('记账'), findsOneWidget);
    expect(find.text('农事'), findsOneWidget);
    expect(find.text('工资'), findsOneWidget);
    expect(find.text('金额与分类'), findsOneWidget);
    expect(find.text('时间与归属'), findsOneWidget);
    expect(find.text('付款方式'), findsOneWidget);
    expect(find.text('备注'), findsOneWidget);
    expect(find.text('保存修改'), findsOneWidget);
  });

  testWidgets('保存成功页展示结果摘要和下一步动作', (tester) async {
    await pumpFlow(tester, const RecordSaveSuccessScreen());

    expect(find.text('记录已保存'), findsOneWidget);
    expect(find.text('已同步到账本和最近记录'), findsOneWidget);
    expect(find.text('饲料采购单'), findsOneWidget);
    expect(find.text('¥3,680.00'), findsOneWidget);
    expect(find.text('5月第2批次'), findsOneWidget);
    expect(find.text('今天'), findsOneWidget);
    expect(find.text('现金'), findsOneWidget);
    expect(find.text('已入账'), findsOneWidget);
    expect(find.text('再记一笔'), findsOneWidget);
    expect(find.text('查看账本'), findsOneWidget);
    expect(find.text('回到首页'), findsOneWidget);
    expect(find.text('完成'), findsOneWidget);
  });

  testWidgets('记录页入口可打开三页闭环并能从成功页切到账本', (tester) async {
    await pumpFlow(
      tester,
      AppShell(dependencies: FakeAppDependencies(), initialIndex: 1),
    );

    await tester.tap(find.text('AI帮我填'));
    await tester.pumpAndSettle();
    expect(find.text('智能确认'), findsOneWidget);
    expect(find.text('首页'), findsNothing);

    await tester.tap(find.text('改一下'));
    await tester.pumpAndSettle();
    expect(find.text('保存修改'), findsOneWidget);

    await tester.tap(find.text('保存修改'));
    await tester.pumpAndSettle();
    expect(find.text('记录已保存'), findsOneWidget);

    await tester.tap(find.text('查看账本'));
    await tester.pumpAndSettle();
    expect(find.text('资金概览'), findsOneWidget);
    expect(find.text('账本'), findsWidgets);
  });
}
