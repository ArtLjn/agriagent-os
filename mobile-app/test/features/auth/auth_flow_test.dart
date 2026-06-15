import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/location/location_service.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/features/auth/auth_flow.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

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
    expect(find.text('MVP功能全部免费'), findsOneWidget);
    expect(find.text('手动记录'), findsOneWidget);
    expect(find.text('AI帮填'), findsOneWidget);
    expect(find.text('账本提醒'), findsOneWidget);

    await tester.tap(find.text('注册并进入'));
    await tester.pump();

    expect(find.text('完善农场信息'), findsOneWidget);
    expect(find.text('农场名称'), findsOneWidget);
    expect(find.text('经营地区'), findsOneWidget);
    expect(find.text('所在城市'), findsNothing);
    expect(find.text('默认天气城市'), findsNothing);
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

  testWidgets('登录页预填开发账号密码并可直接进入主应用', (tester) async {
    final dependencies = FakeAppDependencies();
    await pumpAuthFlow(tester, dependencies: dependencies);

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
    expect(find.text('完善农场信息'), findsOneWidget);
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
      {'/settings': settingsResponse, '/api/app/version': versionResponse},
      statusCodes: {'/auth/me': 500},
    );
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
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
    expect(find.text('完善农场信息'), findsOneWidget);
    expect(find.text('经营地区'), findsOneWidget);
    expect(find.text('首页'), findsNothing);
  });

  testWidgets('首次设置可用当前位置初始化经营地区并进入主应用', (tester) async {
    final location = FakeLocationService(
      suggestion: const FarmLocationSuggestion(city: '邳州市'),
    );
    final adapter = RecordingAdapter({
      '/auth/me': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': null,
        },
      },
      'PUT /auth/me/farm-location': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': '邳州市',
        },
      },
      '/settings': settingsResponse,
      '/api/app/version': versionResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final dependencies = FakeAppDependencies(
      profile: ProfileRepository(ApiClient(dio: dio)),
      location: location,
    );

    await pumpAuthFlow(tester, dependencies: dependencies);
    await tester.tap(find.text('登录'));
    await tester.pumpAndSettle();

    expect(find.text('完善农场信息'), findsOneWidget);
    await tester.pumpAndSettle();
    expect(find.text('邳州市'), findsOneWidget);
    await tester.tap(find.text('开始使用'));
    await tester.pumpAndSettle();

    expect(location.requestCalls, 1);
    expect(adapter.find('PUT', '/auth/me/farm-location').data, {
      'location': '邳州市',
    });
    expect(find.text('首页'), findsWidgets);
  });

  testWidgets('首次设置定位失败时保留手动填写和稍后进入', (tester) async {
    final location = FakeLocationService();
    final adapter = RecordingAdapter({
      '/auth/me': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': null,
        },
      },
      'PUT /auth/me/farm-location': userResponse,
      '/settings': settingsResponse,
      '/api/app/version': versionResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
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

    expect(adapter.requests.where((r) => r.path == '/auth/me/farm-location'),
        isEmpty);
    expect(find.text('首页'), findsWidgets);
  });

  testWidgets('首次设置可通过城市选择器保存经营地区', (tester) async {
    final location = FakeLocationService();
    final adapter = RecordingAdapter({
      '/auth/me': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': null,
        },
      },
      'PUT /auth/me/farm-location': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': '睢宁县',
        },
      },
      '/settings': settingsResponse,
      '/api/app/version': versionResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
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
      '睢宁',
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('睢宁县'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('开始使用'));
    await tester.pumpAndSettle();

    expect(adapter.find('PUT', '/auth/me/farm-location').data, {
      'location': '睢宁县',
      'lat': 34.20442,
      'lon': 117.28386,
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
    '/auth/me': {
      ...userResponse,
      'farm': {
        'id': 1,
        'name': '农友的农场',
        'location': location,
      },
    },
    '/settings': settingsResponse,
    '/api/app/version': versionResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
  dio.httpClientAdapter = adapter;
  return ProfileRepository(ApiClient(dio: dio));
}
