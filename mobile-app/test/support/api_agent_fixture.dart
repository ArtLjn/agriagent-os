part of 'api_test_fixtures.dart';

final conversationResponse = {
  'id': 1,
  'session_id': 's1',
  'status': 'active',
  'title': '问答',
  'preview': '今天浇水吗',
  'category': '对话',
  'created_at': '2026-06-08T08:00:00',
  'last_active_at': '2026-06-08T08:01:00',
};

final messageResponse = {
  'id': 2,
  'role': 'assistant',
  'content': '建议傍晚浇水',
  'skills': ['weather'],
  'pending_action': null,
  'created_at': '2026-06-08T08:02:00',
};

final yayaSkillsResponse = {
  'items': [
    {
      'key': 'create_cost_record',
      'title': '智能记账',
      'description': '一句话生成账本记录',
      'category': '记录',
      'icon': 'receipt-yuan',
      'icon_color': 'green',
      'recommended': true,
      'enabled': true,
    }
  ],
  'total': 1,
};
