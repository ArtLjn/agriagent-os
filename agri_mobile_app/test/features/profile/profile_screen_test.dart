import 'dart:async';

import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/location/location_service.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/features/profile/profile_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart'
    show RecordingAdapter, settingsResponse, userResponse, versionResponse;
import '../../support/fake_app_dependencies.dart'
    show FakeLocationService, setMockAppPackageInfo;

void main() {
  testWidgets('我的页面展示接口资料、AI 偏好和设置', (tester) async {
    setMockAppPackageInfo(version: '0.1.0', buildNumber: '1');
    final repository = _profileRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: ProfileScreen(repository: repository)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('我的'), findsOneWidget);
    expect(find.text('农友'), findsOneWidget);
    expect(find.text('13800138000'), findsOneWidget);
    expect(find.text('睢宁县'), findsOneWidget);
    expect(find.text('正常'), findsWidgets);
    expect(find.text('active'), findsNothing);
    expect(find.text('发现新版本 0.1.0'), findsNothing);
    expect(find.text('版本更新检测'), findsNothing);
    expect(find.text('更新说明'), findsNothing);
    expect(find.text('下载地址'), findsNothing);
    expect(find.text('https://example.test/app.apk'), findsNothing);
    expect(find.text('经营地区'), findsOneWidget);
    expect(find.text('所在城市'), findsNothing);
    expect(find.text('默认天气'), findsNothing);
    expect(find.text('数据同步'), findsNothing);
    expect(find.text('AI 偏好设置'), findsNothing);
    expect(find.text('回答风格'), findsOneWidget);
    expect(find.text('温暖陪伴型'), findsOneWidget);
    expect(find.text('分析深度'), findsNothing);
    expect(find.text('自动生成报表'), findsNothing);
    expect(find.text('数据备份与恢复'), findsNothing);
    expect(find.text('消息通知'), findsNothing);
    expect(find.text('关于田掌柜'), findsOneWidget);
    expect(find.text('完善农场资料'), findsNothing);
    expect(find.text('退出登录'), findsNothing);
  });

  testWidgets('关于页展示已安装版本与开源许可', (tester) async {
    setMockAppPackageInfo(version: '0.1.0', buildNumber: '1');
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: ProfileScreen(repository: _profileRepository())),
      ),
    );
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('关于田掌柜'));
    await tester.tap(find.text('关于田掌柜'));
    await tester.pumpAndSettle();

    expect(find.text('关于田掌柜'), findsWidgets);
    expect(find.text('田掌柜'), findsWidgets);
    expect(find.text('当前版本'), findsOneWidget);
    expect(find.text('v0.1.0 (1)'), findsOneWidget);
    expect(find.text('开源许可'), findsOneWidget);
    expect(find.text('立即更新'), findsNothing);
    expect(find.text('稍后'), findsNothing);
    expect(find.text('强制更新'), findsNothing);
    expect(find.text('农场管家'), findsNothing);
    expect(find.text('https://example.test/app.apk'), findsNothing);
  });

  testWidgets('关于页读取本机版本而非更新服务', (tester) async {
    setMockAppPackageInfo(version: '1.2.7', buildNumber: '13');
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ProfileScreen(
            repository: _profileRepository(
              version: {
                'latest_version': '1.2.7',
                'latest_version_code': 13,
                'download_url': 'https://example.test/app.apk',
                'changelog': '更新至 v1.2.7',
                'force_update': false,
              },
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('已是最新 1.2.7'), findsNothing);

    await tester.ensureVisible(find.text('关于田掌柜'));
    await tester.tap(find.text('关于田掌柜'));
    await tester.pumpAndSettle();

    expect(find.text('当前版本'), findsOneWidget);
    expect(find.text('v1.2.7 (13)'), findsOneWidget);
    expect(find.text('开源许可'), findsOneWidget);
    expect(find.text('发现新版本'), findsNothing);
    expect(find.text('立即更新'), findsNothing);
  });

  testWidgets('关于页开源许可在窄屏大字号下可打开并返回', (tester) async {
    setMockAppPackageInfo(version: '1.2.7', buildNumber: '13');
    tester.view.physicalSize = const Size(320, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(
      builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context)
              .copyWith(textScaler: const TextScaler.linear(1.3)),
          child: child!),
      home: const AboutAppPage(),
    ));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('开源许可'));
    await tester.tap(find.text('开源许可'));
    await tester.pumpAndSettle();
    expect(find.byType(LicensePage), findsOneWidget);
    expect(tester.takeException(), isNull);
    Navigator.of(tester.element(find.byType(LicensePage))).pop();
    await tester.pumpAndSettle();
    expect(find.text('v1.2.7 (13)'), findsOneWidget);
  });

  testWidgets('回答风格保存中防止重复操作，失败后保留原设置并允许重试', (tester) async {
    setMockAppPackageInfo();
    final pending = Completer<Object?>();
    final adapter = RecordingAdapter({
      '/users/me': userResponse,
      '/users/me/settings': settingsResponse,
      'PATCH /users/me/settings': pending.future,
    }, statusCodes: {
      'PATCH /users/me/settings': 500
    });
    final dio = Dio()..httpClientAdapter = adapter;
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: ProfileScreen(
                repository: ProfileRepository(ApiClient(dio: dio))))));
    await tester.pumpAndSettle();
    await tester.tap(find.text('回答风格'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('冷静专业型'));
    await tester.pumpAndSettle();
    expect(find.text('正在处理…'), findsOneWidget);
    await tester.tap(find.text('回答风格'));
    await tester.pump();
    expect(adapter.requests.where((request) => request.method == 'PATCH'),
        hasLength(1));
    expect(find.text('冷静专业型'), findsNothing);
    pending.complete({'code': 'SETTINGS_UNAVAILABLE', 'message': '暂时无法保存'});
    await tester.pumpAndSettle();
    expect(find.text('操作未完成，请稍后重试'), findsOneWidget);
    expect(find.text('温暖陪伴型'), findsOneWidget);
    await tester.tap(find.text('回答风格'));
    await tester.pumpAndSettle();
    expect(find.text('冷静专业型'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('我的页面传入退出回调后展示退出登录入口', (tester) async {
    setMockAppPackageInfo(version: '0.1.0', buildNumber: '1');
    var logoutCalls = 0;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ProfileScreen(
            repository: _profileRepository(),
            onLogout: () async {
              logoutCalls += 1;
            },
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('退出登录'));
    await tester.tap(find.text('退出登录'));
    await tester.pump();

    expect(find.text('退出登录'), findsOneWidget);
    expect(logoutCalls, 1);
  });

  testWidgets('点击经营地区可通过城市选择器保存新地区', (tester) async {
    setMockAppPackageInfo(version: '0.1.0', buildNumber: '1');
    final adapter = RecordingAdapter({
      '/users/me': userResponse,
      '/users/me/settings': settingsResponse,
      '/api/app/version': versionResponse,
      'PATCH /farms/1/location': {
        'id': 1,
        'name': '农友的农场',
        'location': '邳州市',
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ProfileScreen(
            repository: ProfileRepository(ApiClient(dio: dio)),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('经营地区'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '邳州');
    await tester.pumpAndSettle();
    await tester.tap(find.text('邳州市'));
    await tester.pumpAndSettle();

    expect(adapter.find('PATCH', '/farms/1/location').data, {
      'location': '邳州市',
      'lat': 34.20442,
      'lon': 117.28386,
    });
  });

  testWidgets('资料页可用重新定位更新经营地区', (tester) async {
    setMockAppPackageInfo(version: '0.1.0', buildNumber: '1');
    final location = FakeLocationService(
      suggestion: const FarmLocationSuggestion(
        city: '邳州市',
        latitude: 34.3142,
        longitude: 117.9586,
      ),
    );
    final adapter = RecordingAdapter({
      '/users/me': userResponse,
      '/users/me/settings': settingsResponse,
      '/api/app/version': versionResponse,
      'PATCH /farms/1/location': {
        'id': 1,
        'name': '农友的农场',
        'location': '邳州市',
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ProfileScreen(
            repository: ProfileRepository(ApiClient(dio: dio)),
            location: location,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('经营地区'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('重新定位'));
    await tester.pumpAndSettle();

    expect(location.requestCalls, 1);
    expect(adapter.find('PATCH', '/farms/1/location').data, {
      'location': '邳州市',
      'lat': 34.3142,
      'lon': 117.9586,
    });
  });

  testWidgets('点击回答风格可保存已支持的助手角色设置', (tester) async {
    setMockAppPackageInfo(version: '0.1.0', buildNumber: '1');
    final adapter = RecordingAdapter({
      '/users/me': userResponse,
      '/users/me/settings': settingsResponse,
      '/api/app/version': versionResponse,
      'PATCH /users/me/settings': {
        ...settingsResponse,
        'assistant_role': 'professional',
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ProfileScreen(
            repository: ProfileRepository(ApiClient(dio: dio)),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('回答风格'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('冷静专业型'));
    await tester.pumpAndSettle();

    expect(adapter.find('PATCH', '/users/me/settings').data, {
      'assistant_role': 'professional',
    });
  });
}

ProfileRepository _profileRepository({Map<String, Object?>? version}) {
  final adapter = RecordingAdapter({
    '/users/me': userResponse,
    '/users/me/settings': settingsResponse,
    '/api/app/version': version ?? versionResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
  dio.httpClientAdapter = adapter;
  return ProfileRepository(ApiClient(dio: dio));
}
