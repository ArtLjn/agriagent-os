import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/location/location_service.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/features/auth/auth_flow.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../support/api_test_fixtures.dart'
    show RecordingAdapter, settingsResponse, userResponse, versionResponse;
import '../../support/fake_app_dependencies.dart';

void main() {
  Future<void> pumpAuthFlow(
    WidgetTester tester, {
    FakeAppDependencies? dependencies,
  }) async {
    setMockAppPackageInfo();
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        home: AuthFlow(dependencies: dependencies ?? FakeAppDependencies()),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('登录注册切换保持品牌位置和各自输入草稿', (tester) async {
    await pumpAuthFlow(tester);
    final brand =
        tester.getRect(find.byKey(const ValueKey('auth-entry-brand')));
    final hero = tester.getRect(find.byKey(const ValueKey('auth-entry-hero')));
    await tester.enterText(find.byType(TextField).at(0), '13800138000');
    await tester.enterText(find.byType(TextField).at(1), 'login-password');
    await tester.ensureVisible(find.text('去注册'));
    await tester.tap(find.text('去注册'));
    await tester.pumpAndSettle();
    expect(
        tester.getRect(find.byKey(const ValueKey('auth-entry-brand'))), brand);
    expect(tester.getRect(find.byKey(const ValueKey('auth-entry-hero'))), hero);
    expect(
        tester.widget<TextField>(find.byType(TextField).at(0)).controller?.text,
        isEmpty);
    expect(
        tester.widget<TextField>(find.byType(TextField).at(1)).controller?.text,
        isEmpty);
    await tester.enterText(find.byType(TextField).at(2), '小李');
    await tester.ensureVisible(find.text('去登录'));
    await tester.tap(find.text('去登录'));
    await tester.pumpAndSettle();
    expect(
        tester.widget<TextField>(find.byType(TextField).at(0)).controller?.text,
        '13800138000');
    expect(
        tester.widget<TextField>(find.byType(TextField).at(1)).controller?.text,
        'login-password');
    await tester.tap(find.text('去注册'));
    await tester.pumpAndSettle();
    expect(
        tester.widget<TextField>(find.byType(TextField).at(2)).controller?.text,
        '小李');
  });

  testWidgets('注册页系统返回键回到登录且保持输入', (tester) async {
    await pumpAuthFlow(tester);
    await tester.tap(find.text('去注册'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(2), '小李');
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('欢迎回来'), findsOneWidget);
    await tester.tap(find.text('去注册'));
    await tester.pumpAndSettle();
    expect(
        tester.widget<TextField>(find.byType(TextField).at(2)).controller?.text,
        '小李');
  });

  testWidgets('认证流程可从登录进入注册、首次设置和主应用', (tester) async {
    await pumpAuthFlow(tester);

    expect(find.text('田掌柜'), findsOneWidget);
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
    expect(find.text('耕耘有记录\n收获心里有数'), findsOneWidget);
    await tester.enterText(find.byType(TextField).at(0), '13900139000');
    await tester.enterText(find.byType(TextField).at(1), 'secret1');

    await tester.tap(find.text('注册并进入'));
    await tester.pump();

    expect(find.text('从你的农场开始'), findsOneWidget);
    expect(find.text('农场名称'), findsNothing);
    expect(find.text('经营地区'), findsOneWidget);
    expect(find.text('所在城市'), findsNothing);
    expect(find.text('默认天气城市'), findsNothing);
    expect(find.text('身份'), findsNothing);
    expect(find.text('农场负责人'), findsNothing);
    expect(find.text('设置经营地区，让天气与农事建议更贴近你。'), findsOneWidget);

    await tester.tap(find.text('开始使用'));
    await tester.pumpAndSettle();

    expect(find.text('首页'), findsWidgets);
    expect(find.text('记录'), findsWidgets);
    expect(find.text('芽芽'), findsWidgets);
    expect(find.text('账本'), findsWidgets);
    expect(find.text('我的'), findsWidgets);
  });

  testWidgets('登录页预填开发账号密码并可直接进入主应用', (tester) async {
    final dependencies = FakeAppDependencies();
    await pumpAuthFlow(tester, dependencies: dependencies);

    final phoneField = tester.widget<TextField>(find.byType(TextField).at(0));
    final passwordField =
        tester.widget<TextField>(find.byType(TextField).at(1));
    expect(phoneField.controller?.text, '19083106293');
    expect(passwordField.controller?.text, 'admin123');

    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();

    expect(dependencies.loginCalls, 1);
    expect(dependencies.lastPhone, '19083106293');
    expect(dependencies.lastPassword, 'admin123');
    expect(dependencies.overviewLoads, 1);
    expect(find.text('首页'), findsWidgets);
    expect(find.text('记录'), findsWidgets);
    expect(find.text('账本'), findsWidgets);
  });

  testWidgets('登录和注册页顶部品牌区保持紧凑', (tester) async {
    await pumpAuthFlow(tester);

    expect(
        tester.getSize(find.byKey(const ValueKey('auth-entry-brand'))).height,
        lessThanOrEqualTo(48));

    await tester.tap(find.text('去注册'));
    await tester.pump();

    expect(
        tester.getSize(find.byKey(const ValueKey('auth-entry-brand'))).height,
        lessThanOrEqualTo(48));
  });

  testWidgets('首页没有建议时可进入芽芽咨询并返回账本', (tester) async {
    await pumpAuthFlow(tester);
    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('问问芽芽'));
    await tester.tap(find.text('问问芽芽'));
    await tester.pumpAndSettle();
    expect(find.text('从一个话题开始'), findsOneWidget);
    await tester.tap(find.text('账本').last);
    await tester.pumpAndSettle();
    expect(find.text('年度净收益'), findsOneWidget);
  });

  testWidgets('登录页允许覆盖开发默认账号密码', (tester) async {
    final dependencies = FakeAppDependencies();
    await pumpAuthFlow(tester, dependencies: dependencies);

    await tester.enterText(find.byType(TextField).at(0), '13800138000');
    await tester.enterText(find.byType(TextField).at(1), 'password');
    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();

    expect(dependencies.lastPhone, '13800138000');
    expect(dependencies.lastPassword, 'password');
  });

  testWidgets('密码输入支持显隐切换并保持登录页布局', (tester) async {
    await pumpAuthFlow(tester);

    final passwordField = find.byType(TextField).at(1);
    expect(tester.widget<TextField>(passwordField).obscureText, isTrue);

    await tester.tap(find.byIcon(LucideIcons.eyeOff));
    await tester.pump();

    expect(tester.widget<TextField>(passwordField).obscureText, isFalse);
    expect(
      tester.widget<IconButton>(find.byType(IconButton).last).tooltip,
      '隐藏密码',
    );
  });

  testWidgets('注册页调用后端注册后进入首次设置', (tester) async {
    final dependencies = FakeAppDependencies();
    await pumpAuthFlow(tester, dependencies: dependencies);

    await tester.tap(find.text('去注册'));
    await tester.pump();
    await tester.enterText(find.byType(TextField).at(0), '13900139000');
    await tester.enterText(find.byType(TextField).at(1), 'secret1');
    await tester.enterText(find.byType(TextField).at(2), '小李');
    await tester.tap(find.text('注册并进入'));
    await tester.pumpAndSettle();

    expect(dependencies.registerCalls, 1);
    expect(dependencies.lastPhone, '13900139000');
    expect(dependencies.lastPassword, 'secret1');
    expect(dependencies.lastNickname, '小李');
    expect(find.text('从你的农场开始'), findsOneWidget);
  });

  testWidgets('登录接口失败时停留登录页并展示错误', (tester) async {
    final dependencies = FakeAppDependencies(loginError: Exception('401'));
    await pumpAuthFlow(tester, dependencies: dependencies);

    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();

    expect(dependencies.loginCalls, 1);
    expect(dependencies.overviewLoads, 0);
    expect(find.text('请求失败，请稍后重试'), findsOneWidget);
    expect(find.text('首页'), findsNothing);
    expect(find.text('账本'), findsNothing);
  });

  testWidgets('启动恢复 session 成功时直接进入主应用', (tester) async {
    final dependencies = FakeAppDependencies(restoreResult: true);
    await pumpAuthFlow(tester, dependencies: dependencies);

    expect(dependencies.restoreCalls, 1);
    expect(dependencies.overviewLoads, 1);
    expect(find.text('首页'), findsWidgets);
    expect(find.text('记录'), findsWidgets);
    expect(find.text('账本'), findsWidgets);
  });

  testWidgets('启动恢复 profile 失败时清理 session 并回登录页', (tester) async {
    final adapter = RecordingAdapter(
      {
        '/users/me/settings': settingsResponse,
        '/api/app/version': versionResponse
      },
      statusCodes: {'/users/me': 500},
    );
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final dependencies = FakeAppDependencies(
      restoreResult: true,
      profile: ProfileRepository(ApiClient(dio: dio)),
    );

    await pumpAuthFlow(tester, dependencies: dependencies);

    expect(dependencies.restoreCalls, 1);
    expect(dependencies.logoutCalls, 1);
    expect(find.text('登录已失效，请重新登录'), findsOneWidget);
    expect(find.text('田掌柜'), findsOneWidget);
    expect(find.text('手机号'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
  });

  testWidgets('登录后默认农场无经营地区时进入首次设置', (tester) async {
    final dependencies = FakeAppDependencies(
      profile: _profileRepositoryWithLocation(null),
    );
    await pumpAuthFlow(tester, dependencies: dependencies);

    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();

    expect(dependencies.loginCalls, 1);
    expect(find.text('从你的农场开始'), findsOneWidget);
    expect(find.text('经营地区'), findsOneWidget);
    expect(find.text('首页'), findsNothing);
  });

  testWidgets('首次设置可用当前位置初始化经营地区并进入主应用', (tester) async {
    final location = FakeLocationService(
      suggestion: const FarmLocationSuggestion(city: '邳州市'),
    );
    final adapter = RecordingAdapter({
      '/users/me': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': null,
        },
      },
      'PATCH /farms/1/location': {
        'id': 1,
        'name': '农友的农场',
        'location': '邳州市',
      },
      '/users/me/settings': settingsResponse,
      '/api/app/version': versionResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final dependencies = FakeAppDependencies(
      profile: ProfileRepository(ApiClient(dio: dio)),
      location: location,
    );

    await pumpAuthFlow(tester, dependencies: dependencies);
    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();

    expect(find.text('从你的农场开始'), findsOneWidget);
    await tester.pumpAndSettle();
    expect(find.text('邳州市'), findsOneWidget);
    await tester.tap(find.text('开始使用'));
    await tester.pumpAndSettle();

    expect(location.requestCalls, 1);
    expect(adapter.find('PATCH', '/farms/1/location').data, {
      'location': '邳州市',
    });
    expect(find.text('首页'), findsWidgets);
  });

  testWidgets('首次设置定位失败时保留手动填写和稍后进入', (tester) async {
    final location = FakeLocationService();
    final adapter = RecordingAdapter({
      '/users/me': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': null,
        },
      },
      'PATCH /farms/1/location': userResponse['farm'],
      '/users/me/settings': settingsResponse,
      '/api/app/version': versionResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final dependencies = FakeAppDependencies(
      profile: ProfileRepository(ApiClient(dio: dio)),
      location: location,
    );

    await pumpAuthFlow(tester, dependencies: dependencies);
    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();

    expect(location.requestCalls, 1);
    expect(find.text('无法获取当前位置，请手动填写经营地区'), findsOneWidget);
    await tester.tap(find.text('稍后再说'));
    await tester.pumpAndSettle();

    expect(
        adapter.requests.where((r) => r.path == '/farms/1/location'), isEmpty);
    expect(find.text('首页'), findsWidgets);
  });

  testWidgets('首次设置可通过城市选择器保存经营地区', (tester) async {
    final location = FakeLocationService();
    final adapter = RecordingAdapter({
      '/users/me': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': null,
        },
      },
      'PATCH /farms/1/location': {
        'id': 1,
        'name': '农友的农场',
        'location': '苏州市虎丘区',
      },
      '/users/me/settings': settingsResponse,
      '/api/app/version': versionResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final dependencies = FakeAppDependencies(
      profile: ProfileRepository(ApiClient(dio: dio)),
      location: location,
    );

    await pumpAuthFlow(tester, dependencies: dependencies);
    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();

    await tester.tap(
      find.byWidgetPredicate(
        (widget) =>
            widget is TextField && widget.decoration?.hintText == '请选择经营地区',
      ),
    );
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byWidgetPredicate(
        (widget) =>
            widget is TextField && widget.decoration?.hintText == '搜索城市或区县',
      ),
      '苏州',
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('苏州市虎丘区'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('开始使用'));
    await tester.pumpAndSettle();

    expect(adapter.find('PATCH', '/farms/1/location').data, {
      'location': '苏州市虎丘区',
      'lat': 31.3296,
      'lon': 120.4342,
    });
    expect(find.text('首页'), findsWidgets);
  });

  testWidgets('退出登录后清理 session 并回到登录页', (tester) async {
    final dependencies = FakeAppDependencies(restoreResult: true);
    await pumpAuthFlow(tester, dependencies: dependencies);

    await tester.tap(find.text('我的').last);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('退出登录'));
    await tester.tap(find.text('退出登录'));
    await tester.pumpAndSettle();

    expect(dependencies.logoutCalls, 1);
    expect(find.text('田掌柜'), findsOneWidget);
    expect(find.text('手机号'), findsOneWidget);
    expect(find.text('首页'), findsNothing);
  });
}

ProfileRepository _profileRepositoryWithLocation(String? location) {
  final adapter = RecordingAdapter({
    '/users/me': {
      ...userResponse,
      'farm': {
        'id': 1,
        'name': '农友的农场',
        'location': location,
      },
    },
    '/users/me/settings': settingsResponse,
    '/api/app/version': versionResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
  dio.httpClientAdapter = adapter;
  return ProfileRepository(ApiClient(dio: dio));
}
