import 'package:farm_manager_app/data/api/api_models.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  test('DailyAdvice 解析 v2 compact 和 detail_view', () {
    final advice = DailyAdvice.fromJson(dailyAdviceResponse);

    expect(advice.overview.score, 82);
    expect(advice.overview.subtitle, '今日天气偏热，请优先安排关键作业。');
    expect(advice.overview.metrics.map((metric) => metric.key), [
      'weather',
      'work_order',
      'pending',
    ]);
    expect(advice.overview.metrics[1].value, '1项');
    expect(advice.items.single.compact.subtitle, '傍晚少量浇水，避开中午高温时段。');
    expect(advice.items.single.detailView.title, '傍晚补水');
    expect(advice.items.single.detailView.evidence.single.sourceType,
        'weather_service');
    expect(advice.items.single.detailView.steps, hasLength(2));
    expect(advice.items.single.detailView.actions.single.type, 'ask_agent');
  });

  test('DailyAdvice 兼容旧 title/detail 响应', () {
    final advice = DailyAdvice.fromJson({
      'preview': '旧建议',
      'items': [
        {'title': '浇水', 'detail': '傍晚少量浇水', 'priority': 1, 'icon': 'water'}
      ],
      'advice': '浇水: 傍晚少量浇水',
    });

    expect(advice.items.single.compact.title, '浇水');
    expect(advice.items.single.compact.subtitle, '傍晚少量浇水');
    expect(advice.items.single.detailView.description, '傍晚少量浇水');
  });
}
