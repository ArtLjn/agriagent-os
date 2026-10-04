import 'dart:async';

import 'package:farm_manager_app/features/auth/login_screen.dart';
import 'package:farm_manager_app/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Future<void> pumpLogin(
    WidgetTester tester, {
    Size size = const Size(390, 844),
    double textScale = 1,
    double keyboardHeight = 0,
    Future<void> Function({required String phone, required String password})?
        onLogin,
    VoidCallback? onRegister,
  }) async {
    tester.view.physicalSize = size;
    tester.view.devicePixelRatio = 1;
    tester.view.viewInsets = FakeViewPadding(bottom: keyboardHeight);
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light(),
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context)
            .copyWith(textScaler: TextScaler.linear(textScale)),
        child: child!,
      ),
      home: LoginScreen(
        onLogin: onLogin ?? ({required phone, required password}) async {},
        onRegister: onRegister ?? () {},
      ),
    ));
    await tester.pumpAndSettle();
  }

  testWidgets('品牌表达清晰，登录和注册入口可见', (tester) async {
    var registered = false;
    await pumpLogin(tester, onRegister: () => registered = true);
    expect(find.text('耕耘有记录\n收获心里有数'), findsOneWidget);
    expect(find.text('欢迎回来'), findsOneWidget);
    expect(find.text('每一份耕耘，都值得被记住'), findsOneWidget);
    await tester.tap(find.text('去注册'));
    expect(registered, isTrue);
    expect(tester.takeException(), isNull);
  });

  testWidgets('登录保留账号编辑和密码显隐', (tester) async {
    String? submittedPhone;
    String? submittedPassword;
    await pumpLogin(tester,
        onLogin: ({required phone, required password}) async {
      submittedPhone = phone;
      submittedPassword = password;
    });
    final password = find.byType(TextField).at(1);
    expect(tester.widget<TextField>(password).obscureText, isTrue);
    await tester.tap(find.byTooltip('显示密码'));
    await tester.pump();
    expect(tester.widget<TextField>(password).obscureText, isFalse);
    await tester.enterText(find.byType(TextField).first, ' 13800138000 ');
    await tester.enterText(password, 'new-password');
    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();
    expect(submittedPhone, '13800138000');
    expect(submittedPassword, 'new-password');
  });

  testWidgets('等待登录时禁用按钮和注册并阻止键盘重复提交', (tester) async {
    final pending = Completer<void>();
    var calls = 0;
    await pumpLogin(tester, onLogin: ({required phone, required password}) {
      calls++;
      return pending.future;
    });
    await tester.tap(find.text('登录'));
    await tester.pump();
    expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNull);
    expect(
        tester
            .widget<TextButton>(find.widgetWithText(TextButton, '去注册'))
            .onPressed,
        isNull);
    tester
        .widget<TextField>(find.byType(TextField).at(1))
        .onSubmitted!('password');
    expect(calls, 1);
    pending.complete();
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNotNull);
  });

  testWidgets('空表单不发请求，接口失败后展示错误并允许重试', (tester) async {
    var calls = 0;
    await pumpLogin(tester,
        onLogin: ({required phone, required password}) async {
      calls++;
      throw Exception('登录失败');
    });
    await tester.enterText(find.byType(TextField).first, '');
    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();
    expect(calls, 0);
    expect(find.text('请填写手机号和密码'), findsOneWidget);
    await tester.enterText(find.byType(TextField).first, '13800138000');
    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();
    expect(calls, 1);
    expect(find.text('请求失败，请稍后重试'), findsOneWidget);
    expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNotNull);
  });

  testWidgets('忘记密码入口显示当前版本的真实支持方式', (tester) async {
    await pumpLogin(tester);
    await tester.tap(find.text('忘记密码'));
    await tester.pumpAndSettle();
    expect(find.text('找回密码'), findsOneWidget);
    expect(find.text('当前版本暂不支持自助重置密码，请联系账号管理员协助处理。'), findsOneWidget);
    await tester.tap(find.text('知道了'));
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsNothing);
  });

  for (final size in [const Size(320, 568), const Size(390, 844)]) {
    testWidgets('小屏与大字体下可滚动到登录操作 $size', (tester) async {
      await pumpLogin(tester, size: size, textScale: 1.3);
      await tester.ensureVisible(find.byType(FilledButton));
      await tester.pumpAndSettle();
      expect(find.byType(FilledButton).hitTestable(), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('键盘弹出后收起插画，登录操作仍可触达', (tester) async {
    await pumpLogin(tester, keyboardHeight: 320);
    expect(find.text('耕耘有记录\n收获心里有数'), findsNothing);
    await tester.tap(find.byType(TextField).at(1));
    await tester.ensureVisible(find.byType(FilledButton));
    await tester.pumpAndSettle();
    expect(find.byType(FilledButton).hitTestable(), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
