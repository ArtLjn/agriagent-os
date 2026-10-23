import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/features/profile/assistant_settings_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import '../../support/api_test_fixtures.dart';

void main() {
  final settings = <String, dynamic>{
    'revision': 2,
    'nickname': '农友',
    'assistant_name': '田掌柜',
    'custom_instructions': '',
    'reply_style': 'default',
    'detail_level': 'balanced',
    'display_format': 'auto',
    'execution_detail_level': 'concise',
    'auto_learn_enabled': false,
    'use_saved_memories': true,
    'loading_greeting_enabled': true,
  };
  testWidgets('设置从 Agent 加载并按版本保存，冲突保留编辑', (tester) async {
    final adapter = RecordingAdapter({
      'GET /me/personalization': settings,
      'GET /me/memories': {'items': [], 'total': 0},
      'PATCH /me/personalization': {
        'detail': {'code': 'memory_version_conflict'}
      },
    }, statusCodes: {
      'PATCH /me/personalization': 409
    });
    final dio = Dio(BaseOptions(baseUrl: 'https://agent.example.test'))
      ..httpClientAdapter = adapter;
    await tester.pumpWidget(MaterialApp(
        home: AssistantSettingsScreen(client: ApiClient(dio: dio))));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, '李师傅');
    await tester.scrollUntilVisible(find.text('保存设置'), 250,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(find.text('保存设置'));
    await tester.pumpAndSettle();
    expect(adapter.find('PATCH', '/me/personalization').data,
        containsPair('expected_revision', 2));
    expect(adapter.find('PATCH', '/me/personalization').data,
        containsPair('nickname', '李师傅'));
    await tester.scrollUntilVisible(find.textContaining('保存失败'), -250,
        scrollable: find.byType(Scrollable).first);
    expect(find.textContaining('保存失败'), findsOneWidget);
    expect(find.text('李师傅'), findsOneWidget);
  });

  testWidgets('候选记忆确认走真实 API 并带记录版本', (tester) async {
    final adapter = RecordingAdapter({
      'GET /me/personalization': settings,
      'GET /me/memories': {
        'items': [
          {
            'memory_id': 'candidate',
            'text': '先看成本',
            'scope': 'user_farm',
            'source_type': 'inferred',
            'status': 'candidate',
            'revision': 3
          }
        ],
        'total': 1
      },
      'PATCH /me/memories/candidate': {'status': 'active'},
    });
    final dio = Dio(BaseOptions(baseUrl: 'https://agent.example.test'))
      ..httpClientAdapter = adapter;
    await tester.pumpWidget(MaterialApp(
        home: AssistantSettingsScreen(client: ApiClient(dio: dio))));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.byIcon(Icons.check), 300,
        scrollable: find.byType(Scrollable).first);
    await tester.tap(find.byIcon(Icons.check));
    await tester.pumpAndSettle();
    expect(adapter.find('PATCH', '/me/memories/candidate').data,
        {'expected_revision': 3, 'status': 'active'});
  });
}
