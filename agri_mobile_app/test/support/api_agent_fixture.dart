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
      'description': '把买肥料、卖货收款、农资赊账等口语描述整理成账本记录。',
      'summary': '一句话记录支出、收入和赊账。',
      'details': '把买肥料、卖货收款、农资赊账等口语描述整理成账本记录，执行前会让你确认关键信息。',
      'examples': ['买化肥花了200元', '今天卖西瓜收入3000'],
      'category': '记录',
      'icon': 'receipt-yuan',
      'icon_color': 'green',
      'recommended': true,
      'enabled': true,
    }
  ],
  'total': 1,
};
