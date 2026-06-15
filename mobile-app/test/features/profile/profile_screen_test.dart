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

    expect(find.bySemanticsLabel('田掌柜'), findsOneWidget);
    expect(find.text('农友'), findsOneWidget);
    expect(find.text('13800138000 · 用户'), findsOneWidget);
    expect(find.text('睢宁县'), findsNWidgets(2));
    expect(find.text('正常'), findsWidgets);
    expect(find.text('active'), findsNothing);
    expect(find.text('发现新版本 0.1.0'), findsOneWidget);
    expect(find.text('版本更新检测'), findsNothing);
    expect(find.text('更新说明'), findsNothing);
    expect(find.text('下载地址'), findsNothing);
    expect(find.text('https://example.test/app.apk'), findsNothing);
    expect(find.text('经营地区'), findsOneWidget);
    expect(find.text('所在城市'), findsNothing);
    expect(find.text('默认天气'), findsNothing);
    expect(find.text('数据同步'), findsOneWidget);
    expect(find.text('AI 偏好设置'), findsOneWidget);
    expect(find.text('回答风格'), findsOneWidget);
    expect(find.text('温暖陪伴型'), findsOneWidget);
    expect(find.text('分析深度'), findsOneWidget);
    expect(find.text('自动生成报表'), findsOneWidget);
    expect(find.text('数据备份与恢复'), findsOneWidget);
    expect(find.text('消息通知'), findsOneWidget);
    expect(find.text('关于田掌柜'), findsOneWidget);
    expect(find.text('完善农场资料'), findsOneWidget);
    expect(find.text('退出登录'), findsNothing);
  });

  testWidgets('点击关于田掌柜进入关于页并弹出更新框但不暴露下载地址', (tester) async {
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
    expect(find.text('版本更新检测'), findsOneWidget);
    expect(find.text('发现新版本'), findsOneWidget);
    expect(find.text('更新至 v0.1.0'), findsWidgets);
    expect(find.text('立即更新'), findsOneWidget);
    expect(find.text('稍后'), findsOneWidget);
    expect(find.text('强制更新'), findsNothing);
    expect(find.text('农场管家'), findsNothing);
    expect(find.text('https://example.test/app.apk'), findsNothing);
  });

  testWidgets('安装包已是最新版本时不弹出更新框', (tester) async {
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

    expect(find.text('已是最新 1.2.7'), findsOneWidget);

    await tester.ensureVisible(find.text('关于田掌柜'));
    await tester.tap(find.text('关于田掌柜'));
    await tester.pumpAndSettle();

    expect(find.text('版本更新检测'), findsOneWidget);
    expect(find.text('当前已是最新版本'), findsOneWidget);
    expect(find.text('发现新版本'), findsNothing);
    expect(find.text('立即更新'), findsNothing);
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
      '/auth/me': userResponse,
      '/settings': settingsResponse,
      '/api/app/version': versionResponse,
      'PUT /auth/me/farm-location': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': '邳州市',
        },
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
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

    expect(adapter.find('PUT', '/auth/me/farm-location').data, {
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
      '/auth/me': userResponse,
      '/settings': settingsResponse,
      '/api/app/version': versionResponse,
      'PUT /auth/me/farm-location': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': '邳州市',
        },
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
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
    expect(adapter.find('PUT', '/auth/me/farm-location').data, {
      'location': '邳州市',
      'lat': 34.3142,
      'lon': 117.9586,
    });
  });
}

ProfileRepository _profileRepository({Map<String, Object?>? version}) {
  final adapter = RecordingAdapter({
    '/auth/me': userResponse,
    '/settings': settingsResponse,
    '/api/app/version': version ?? versionResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
  dio.httpClientAdapter = adapter;
  return ProfileRepository(ApiClient(dio: dio));
}
