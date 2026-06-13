import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/dashboard_repository.dart';
import 'package:farm_manager_app/features/home/home_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  test('首页 controller 聚合建议、天气、作业单和未结人工摘要', () async {
    final adapter = RecordingAdapter({
      '/agent/daily': dailyAdviceResponse,
      '/weather/forecast': weatherResponse,
      '/planting/work-orders': paginatedWorkOrdersResponse,
      '/planting/labor/unsettled-summary': unsettledLaborSummaryResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = HomeController(
      repository: DashboardRepository(ApiClient(dio: dio)),
    );

    final model = await controller.load();

    expect(model.headline, '注意控水');
    expect(model.weatherText, '晴');
    expect(model.suggestions, isNotEmpty);
    expect(model.suggestions.first.title, '浇水');
    expect(model.workOrderCountText, '1项');
    expect(model.unsettledLaborText, '¥200');
    expect(model.riskText, '1项');
    expect(adapter.find('GET', '/planting/work-orders').query['size'], 10);
    expect(adapter.find('GET', '/weather/forecast').query, {'days': 7});
  });

  test('天气接口失败时首页仍展示其他数据', () async {
    final adapter = RecordingAdapter({
      '/agent/daily': dailyAdviceResponse,
      'GET /weather/forecast': {'detail': '内部服务器错误'},
      '/planting/work-orders': paginatedWorkOrdersResponse,
      '/planting/labor/unsettled-summary': unsettledLaborSummaryResponse,
    }, statusCodes: {
      'GET /weather/forecast': 500
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = HomeController(
      repository: DashboardRepository(ApiClient(dio: dio)),
    );

    final model = await controller.load();

    expect(model.headline, '注意控水');
    expect(model.weatherText, '暂无天气');
    expect(model.workOrderCountText, '1项');
  });

  test('首页天气兼容后端真实 daily 结构', () async {
    final adapter = RecordingAdapter({
      '/agent/daily': dailyAdviceResponse,
      '/weather/forecast': backendWeatherResponse,
      '/planting/work-orders': paginatedWorkOrdersResponse,
      '/planting/labor/unsettled-summary': unsettledLaborSummaryResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = HomeController(
      repository: DashboardRepository(ApiClient(dio: dio)),
    );

    final model = await controller.load();

    expect(model.weatherText, '高温 32℃');
    expect(model.scoreCaption, '高温 32℃ · 1项作业');
  });
}
