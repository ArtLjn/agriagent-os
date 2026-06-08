import 'package:farm_manager_app/features/auth/auth_flow.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Future<void> pumpAuthFlow(WidgetTester tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const MaterialApp(home: AuthFlow()));
  }

  testWidgets('认证流程可从登录进入注册、首次设置和主应用', (tester) async {
    await pumpAuthFlow(tester);

    expect(find.text('农场管家'), findsOneWidget);
    expect(find.text('把农场记录得更轻松'), findsOneWidget);
    expect(find.text('手机号'), findsOneWidget);
    expect(find.text('密码'), findsOneWidget);
    expect(find.text('忘记密码'), findsOneWidget);
    expect(find.text('数据仅用于你的农场记录'), findsOneWidget);

    await tester.tap(find.text('去注册'));
    await tester.pump();

    expect(find.text('创建账号'), findsOneWidget);
    expect(find.text('先建账号，记录可以慢慢补'), findsOneWidget);
    expect(find.text('设置密码'), findsOneWidget);
    expect(find.text('昵称'), findsOneWidget);
    expect(find.text('MVP功能全部免费'), findsOneWidget);
    expect(find.text('手动记录'), findsOneWidget);
    expect(find.text('AI帮填'), findsOneWidget);
    expect(find.text('账本提醒'), findsOneWidget);

    await tester.tap(find.text('注册并进入'));
    await tester.pump();

    expect(find.text('完善农场信息'), findsOneWidget);
    expect(find.text('农场名称'), findsOneWidget);
    expect(find.text('所在城市'), findsOneWidget);
    expect(find.text('默认天气城市'), findsOneWidget);
    expect(find.text('身份'), findsOneWidget);
    expect(find.text('农场负责人'), findsOneWidget);
    expect(find.text('可稍后在我的中修改'), findsOneWidget);

    await tester.tap(find.text('开始使用'));
    await tester.pumpAndSettle();

    expect(find.text('首页'), findsWidgets);
    expect(find.text('记录'), findsWidgets);
    expect(find.text('芽芽'), findsWidgets);
    expect(find.text('账本'), findsWidgets);
    expect(find.text('我的'), findsWidgets);
  });

  testWidgets('登录页可以直接进入主应用', (tester) async {
    await pumpAuthFlow(tester);

    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();

    expect(find.text('首页'), findsWidgets);
    expect(find.text('记录'), findsWidgets);
    expect(find.text('账本'), findsWidgets);
  });
}
