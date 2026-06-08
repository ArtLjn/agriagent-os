import 'package:farm_manager_app/features/profile/profile_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('我的页面展示资料、MVP 免费状态、AI 偏好和设置', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: ProfileScreen()));

    expect(find.text('农场管家'), findsOneWidget);
    expect(find.text('张三'), findsOneWidget);
    expect(find.text('农场负责人'), findsOneWidget);
    expect(find.text('春季西瓜基地'), findsOneWidget);
    expect(find.text('MVP免费版'), findsOneWidget);
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
  });
}
