import 'package:farm_manager_app/features/profile/profile_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('我的页面展示成熟产品常规设置入口', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ProfileScreen()));

    expect(find.text('我的'), findsOneWidget);
    expect(find.text('账号、农场、偏好与服务'), findsOneWidget);
    expect(find.text('经营者'), findsOneWidget);
    expect(find.text('芽芽连续运行'), findsOneWidget);
    expect(find.text('芽芽偏好'), findsOneWidget);
    expect(find.text('消息提醒'), findsOneWidget);
    expect(find.text('账号安全'), findsOneWidget);
    expect(find.text('帮助中心'), findsOneWidget);
  });
}
