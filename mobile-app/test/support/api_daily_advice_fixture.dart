part of 'api_test_fixtures.dart';

final dailyAdviceResponse = {
  'cycle_id': 7,
  'preview': '注意控水',
  'overview': {
    'score': 82,
    'subtitle': '今日天气偏热，请优先安排关键作业。',
    'metrics': [
      {'key': 'weather', 'label': '天气', 'value': '晴'},
      {'key': 'work_order', 'label': '作业', 'value': '1项'},
      {'key': 'pending', 'label': '待处理', 'value': '1项'},
    ],
  },
  'items': [
    {
      'id': 'weather:hot',
      'category': 'weather',
      'level': 'urgent',
      'source_type': 'weather_service',
      'source_id': 12,
      'title': '浇水',
      'detail': '傍晚少量浇水',
      'priority': 1,
      'icon': 'CloudSun',
      'compact': {
        'title': '浇水',
        'subtitle': '傍晚少量浇水，避开中午高温时段。',
        'icon': 'CloudSun',
        'icon_color': 'blue',
      },
      'detail_view': {
        'title': '傍晚补水',
        'description': '今天高温明显，建议傍晚少量补水并观察土壤墒情。',
        'hero_badges': [
          {
            'label': '天气',
            'value': '高温 32℃',
            'level': 'urgent',
            'icon': 'Thermometer'
          },
          {'label': '位置', 'value': '寿光', 'level': 'normal', 'icon': 'MapPin'},
        ],
        'evidence': [
          {
            'title': '天气',
            'description': '晴热少雨，需要避开中午补水。',
            'source_type': 'weather_service',
            'source_id': 12,
          }
        ],
        'steps': [
          {'order': 1, 'title': '查看墒情', 'description': '确认表层土壤干湿。'},
          {'order': 2, 'title': '傍晚补水', 'description': '少量多次，避免积水。'},
        ],
        'related': [
          {
            'title': '天气风险',
            'description': '高温待关注',
            'source_type': 'weather_service',
            'source_id': 12,
          }
        ],
        'actions': [
          {
            'type': 'ask_agent',
            'label': '问问芽芽',
            'payload': {'candidate_id': 'weather:hot'}
          },
        ],
      },
    }
  ],
  'generation': {
    'schema_version': 'daily_advice_v2',
    'mode': 'llm',
    'retry_count': 0,
    'cache_hit': false,
    'candidate_fingerprint': 'fixture',
  },
  'created_at': '2026-06-08T08:00:00',
  'advice': '浇水: 傍晚少量浇水',
};
