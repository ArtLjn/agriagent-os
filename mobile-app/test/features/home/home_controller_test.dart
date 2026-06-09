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
    expect(model.weatherText, contains('寿光'));
    expect(model.suggestions, isNotEmpty);
    expect(model.suggestions.first.title, '浇水');
    expect(model.workOrderCountText, '1项');
    expect(model.unsettledLaborText, '¥200');
    expect(adapter.find('GET', '/planting/work-orders').query['size'], 10);
  });
}
