import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/dashboard_repository.dart';
import 'package:farm_manager_app/features/home/home_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  test('首页按当前 v2 协议聚合天气、作业和未结人工', () async {
    final adapter = _adapter(v2WeatherResponse);
    final model = await _load(adapter);

    expect(model.headline, '苏州暂无每日 AI 建议');
    expect(model.scoreText, '--');
    expect(model.weatherText, '17～32℃');
    expect(model.weatherCondition, WeatherCondition.partlyCloudy);
    expect(model.weatherDescription, '多云');
    expect(model.workOrderCountText, '1项');
    expect(model.unsettledLaborText, '¥200');
    expect(adapter.find('GET', '/work-orders').query['page_size'], 10);
    expect(adapter.find('GET', '/weather').query, {'days': 7});
  });

  test('天气请求失败保留其他数据，不伪造天气和温度', () async {
    final model = await _load(_adapter({'code': 'fetch_failed'}, status: 503));
    expect(model.weatherText, '暂无天气');
    expect(model.weatherCondition, WeatherCondition.unknown);
    expect(model.workOrderCountText, '1项');
    expect(model.unsettledLaborText, '¥200');
  });

  for (final temperature in [0, -2.4, '19.8']) {
    test('日温度范围缺失时显示实时气温 $temperature', () async {
      final model = await _load(_adapter({
        ...v2WeatherResponse,
        'current_temp': temperature,
        'daily': [
          {'desc': '多云', 'code': 2}
        ],
      }));
      final value = num.parse('$temperature').round();
      expect(model.weatherText, '$value℃');
    });
  }

  test('优先展示当天温度区间，实时气温缺失也可显示范围', () async {
    final model =
        await _load(_adapter({...v2WeatherResponse, 'current_temp': null}));
    expect(model.weatherText, '17～32℃');
  });

  test('兼容旧实时字段，不能仅因温度偏高推断晴天', () async {
    final model = await _load(_adapter(backendWeatherResponse));
    expect(model.weatherText, '20℃');
    expect(model.weatherCondition, WeatherCondition.unknown);
  });

  test('缺少温度只展示实际天气，不显示虚构的零度', () async {
    final model = await _load(_adapter(weatherResponse));
    expect(model.weatherText, '晴');
    expect(model.weatherCondition, WeatherCondition.sunny);
  });

  test('兼容后端 days 字段和字符串温度', () async {
    final model = await _load(_adapter({
      'current_temp': '25.2',
      'days': [
        {'weather_text': '阴', 'weather_code': 3}
      ],
    }));
    expect(model.weatherText, '25℃');
    expect(model.weatherCondition, WeatherCondition.cloudy);
  });

  for (final entry in {
    '晴': WeatherCondition.sunny,
    '晴间多云': WeatherCondition.partlyCloudy,
    '阴': WeatherCondition.cloudy,
    '冻雨': WeatherCondition.rain,
    '阵雪': WeatherCondition.snow,
    '雷暴伴冰雹': WeatherCondition.thunder,
    '冻雾': WeatherCondition.fog,
    '未知': WeatherCondition.unknown,
  }.entries) {
    test('和风天气描述 ${entry.key} 映射正确类型', () async {
      final model = await _load(_adapter({
        'current_temp': 22,
        'daily': [
          {'desc': entry.key, 'code': null}
        ],
      }));
      expect(model.weatherCondition, entry.value);
    });
  }

  for (final entry in {
    0: WeatherCondition.sunny,
    2: WeatherCondition.partlyCloudy,
    3: WeatherCondition.cloudy,
    48: WeatherCondition.fog,
    67: WeatherCondition.rain,
    77: WeatherCondition.snow,
    95: WeatherCondition.thunder,
    999: WeatherCondition.unknown,
  }.entries) {
    test('Open-Meteo WMO 代码 ${entry.key} 映射正确类型', () async {
      final model = await _load(_adapter({
        'current_temp': 22,
        'daily': [
          {'desc': '未知', 'code': entry.key}
        ],
      }));
      expect(model.weatherCondition, entry.value);
    });
  }

  test('接口业务错误和非法温度保留不可用状态', () async {
    for (final response in [
      {'error': 'unknown_location', 'message': '地区不可用'},
      {'current_temp': 'NaN', 'daily': []},
      {'current_temp': 'Infinity', 'daily': []},
    ]) {
      final model = await _load(_adapter(response));
      expect(model.weatherText, '暂无天气');
      expect(model.weatherCondition, WeatherCondition.unknown);
    }
  });
}

RecordingAdapter _adapter(Map<String, dynamic> weather, {int status = 200}) {
  return RecordingAdapter({
    '/dashboard': {'location': '苏州', 'active_cycles': []},
    '/weather': weather,
    '/work-orders': paginatedWorkOrdersResponse,
    '/labor/unsettled-summary': unsettledLaborSummaryResponse,
  }, statusCodes: {
    '/weather': status
  });
}

Future<HomeViewModel> _load(RecordingAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'http://10.0.2.2:9876/api/v2'))
    ..httpClientAdapter = adapter;
  return HomeController(repository: DashboardRepository(ApiClient(dio: dio)))
      .load();
}
