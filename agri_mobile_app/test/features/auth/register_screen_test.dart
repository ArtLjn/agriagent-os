import 'dart:async';

import 'package:dio/dio.dart';
import 'package:farm_manager_app/features/auth/register_screen.dart';
import 'package:farm_manager_app/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Future<void> pumpRegister(
    WidgetTester tester, {
    Size size = const Size(390, 844),
    double keyboardHeight = 0,
    double textScale = 1,
    Future<void> Function(
            {required String phone,
            required String password,
            required String nickname})?
        onRegister,
    VoidCallback? onLogin,
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
      home: RegisterScreen(
        onRegister: onRegister ??
            ({required phone, required password, required nickname}) async {},
        onLogin: onLogin ?? () {},
      ),
    ));
    await tester.pumpAndSettle();
  }

  testWidgets('注册沿用登录品牌表达和隐私提示，可返回登录', (tester) async {
    var switched = false;
    await pumpRegister(tester, onLogin: () => switched = true);
    expect(find.text('田掌柜'), findsOneWidget);
    expect(find.text('耕耘有记录\n收获心里有数'), findsOneWidget);
    expect(find.text('创建账号'), findsOneWidget);
    expect(find.text('数据仅用于你的农场记录'), findsOneWidget);
    await tester.ensureVisible(find.text('去登录'));
    await tester.tap(find.text('去登录'));
    expect(switched, isTrue);
  });

  testWidgets('注册提交实际填写的信息，昵称空白时使用农友', (tester) async {
    Map<String, String>? submitted;
    await pumpRegister(tester, onRegister: (
        {required phone, required password, required nickname}) async {
      submitted = {'phone': phone, 'password': password, 'nickname': nickname};
    });
    await tester.enterText(find.byType(TextField).at(0), ' 13900139000 ');
    await tester.enterText(find.byType(TextField).at(1), 'secret1');
    await tester.enterText(find.byType(TextField).at(2), '   ');
    await tester.ensureVisible(find.text('注册并进入'));
    await tester.tap(find.text('注册并进入'));
    await tester.pumpAndSettle();
    expect(submitted,
        {'phone': '13900139000', 'password': 'secret1', 'nickname': '农友'});
    await tester.enterText(find.byType(TextField).at(2), ' 小李 ');
    tester.widget<TextField>(find.byType(TextField).at(2)).onSubmitted!('小李');
    await tester.pumpAndSettle();
    expect(submitted?['nickname'], '小李');
  });

  testWidgets('注册密码可显隐，空必填项不请求后端', (tester) async {
    var calls = 0;
    await pumpRegister(tester, onRegister: (
        {required phone, required password, required nickname}) async {
      calls++;
    });
    final password = find.byType(TextField).at(1);
    expect(tester.widget<TextField>(password).obscureText, isTrue);
    await tester.tap(find.byTooltip('显示密码'));
    await tester.pump();
    expect(tester.widget<TextField>(password).obscureText, isFalse);
    await tester.ensureVisible(find.text('注册并进入'));
    await tester.tap(find.text('注册并进入'));
    await tester.pumpAndSettle();
    expect(find.text('请填写手机号和密码'), findsOneWidget);
    expect(calls, 0);
  });

  testWidgets('注册等待时锁定表单和切换入口，防止重复创建账号', (tester) async {
    final pending = Completer<void>();
    var calls = 0;
    await pumpRegister(tester,
        onRegister: ({required phone, required password, required nickname}) {
      calls++;
      return pending.future;
    });
    await tester.enterText(find.byType(TextField).at(0), '13900139000');
    await tester.enterText(find.byType(TextField).at(1), 'secret1');
    await tester.ensureVisible(find.text('注册并进入'));
    await tester.tap(find.text('注册并进入'));
    await tester.pump();
    expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNull);
    expect(
        tester
            .widget<TextButton>(find.widgetWithText(TextButton, '去登录'))
            .onPressed,
        isNull);
    expect(tester.widget<TextField>(find.byType(TextField).first).readOnly,
        isTrue);
    tester.widget<TextField>(find.byType(TextField).at(2)).onSubmitted!('小李');
    expect(calls, 1);
    pending.complete();
    await tester.pumpAndSettle();
    expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNotNull);
  });

  testWidgets('展示后端注册失败原因，保留输入并允许修改重试', (tester) async {
    await pumpRegister(tester, onRegister: (
        {required phone, required password, required nickname}) async {
      final options = RequestOptions(path: '/auth/register');
      throw DioException.badResponse(
        statusCode: 409,
        requestOptions: options,
        response: Response(requestOptions: options, statusCode: 409, data: {
          'detail': {'message': '手机号已注册'}
        }),
      );
    });
    await tester.enterText(find.byType(TextField).at(0), '13900139000');
    await tester.enterText(find.byType(TextField).at(1), 'secret1');
    await tester.ensureVisible(find.text('注册并进入'));
    await tester.tap(find.text('注册并进入'));
    await tester.pumpAndSettle();
    expect(find.text('手机号已注册'), findsOneWidget);
    expect(
        tester.widget<TextField>(find.byType(TextField).first).controller?.text,
        '13900139000');
    expect(tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
        isNotNull);
  });

  for (final size in [const Size(320, 568), const Size(390, 844)]) {
    testWidgets('注册在小屏和大字体下可滚动到提交按钮 $size', (tester) async {
      await pumpRegister(tester, size: size, textScale: 1.3);
      await tester.ensureVisible(find.byType(FilledButton));
      await tester.pumpAndSettle();
      expect(find.byType(FilledButton).hitTestable(), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('注册键盘弹出后隐藏插画，昵称和提交按钮可触达', (tester) async {
    await pumpRegister(tester, keyboardHeight: 320);
    expect(find.text('耕耘有记录\n收获心里有数'), findsNothing);
    await tester.ensureVisible(find.byType(TextField).at(2));
    await tester.tap(find.byType(TextField).at(2));
    await tester.ensureVisible(find.byType(FilledButton));
    await tester.pumpAndSettle();
    expect(find.byType(FilledButton).hitTestable(), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
