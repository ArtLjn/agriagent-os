import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/features/profile/profile_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../data/repositories/app_api_integration_test.dart'
    show RecordingAdapter, settingsResponse, userResponse, versionResponse;

void main() {
  testWidgets('我的页面展示接口资料、AI 偏好和设置', (tester) async {
    final repository = _profileRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: ProfileScreen(repository: repository)),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('农场管家'), findsOneWidget);
    expect(find.text('农友'), findsOneWidget);
    expect(find.text('13800138000 · user'), findsOneWidget);
    expect(find.text('寿光'), findsNWidgets(3));
    expect(find.text('active'), findsOneWidget);
    expect(find.text('版本 0.1.0'), findsOneWidget);
    expect(find.text('所在城市'), findsOneWidget);
    expect(find.text('默认天气'), findsOneWidget);
    expect(find.text('数据同步'), findsOneWidget);
    expect(find.text('AI 偏好设置'), findsOneWidget);
    expect(find.text('回答风格'), findsOneWidget);
    expect(find.text('分析深度'), findsOneWidget);
    expect(find.text('自动生成报表'), findsOneWidget);
    expect(find.text('数据备份与恢复'), findsOneWidget);
    expect(find.text('消息通知'), findsOneWidget);
    expect(find.text('关于农场管家'), findsOneWidget);
    expect(find.text('完善农场资料'), findsOneWidget);
    expect(find.text('退出登录'), findsNothing);
  });

  testWidgets('我的页面传入退出回调后展示退出登录入口', (tester) async {
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
}

ProfileRepository _profileRepository() {
  final adapter = RecordingAdapter({
    '/auth/me': userResponse,
    '/settings': settingsResponse,
    '/api/app/version': versionResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
  dio.httpClientAdapter = adapter;
  return ProfileRepository(ApiClient(dio: dio));
}
