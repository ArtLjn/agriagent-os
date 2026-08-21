import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/dashboard_repository.dart';
import 'package:farm_manager_app/data/repositories/location_repository.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/data/repositories/workbench_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  test('Business v2 列表接口使用新资源名和 page_size', () async {
    final adapter = RecordingAdapter({
      '/cost-records': {'items': [], 'total': 0},
      '/crop-cycles': {'items': [], 'total': 0},
      '/work-orders': {'items': [], 'total': 0},
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'))
      ..httpClientAdapter = adapter;
    final client = ApiClient(dio: dio);

    await BillingRepository(client).listCosts(size: 12);
    await WorkbenchRepository(client).listCycles(size: 13);
    await DashboardRepository(client).getWorkOrders(size: 14);

    expect(adapter.find('GET', '/cost-records').query['page_size'], 12);
    expect(adapter.find('GET', '/crop-cycles').query['page_size'], 13);
    expect(adapter.find('GET', '/work-orders').query['page_size'], 14);
  });

  test('Business v2 用户、城市搜索和天气使用当前契约', () async {
    final adapter = RecordingAdapter({
      '/users/me': userResponse,
      '/locations/search': {
        'items': [
          {'name': '虎丘区', 'full_name': '苏州市虎丘区', 'lat': 31.3, 'lon': 120.4},
        ],
      },
      '/weather': {'location': '苏州', 'daily': []},
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'))
      ..httpClientAdapter = adapter;
    final client = ApiClient(dio: dio);

    await ProfileRepository(client).getProfile();
    final locations = await LocationRepository(client).searchLocations('虎丘');
    await DashboardRepository(client).getForecast();

    expect(adapter.find('GET', '/users/me').path, '/users/me');
    expect(adapter.find('GET', '/locations/search').query['keyword'], '虎丘');
    expect(adapter.find('GET', '/weather').query['days'], 7);
    expect(locations.single.name, '苏州市虎丘区');
  });

  test('v2 缺少智能帮填时返回明确不可用错误', () async {
    final repository = WorkbenchRepository(ApiClient());

    expect(
      () => repository.parseSmartFill(scene: 'ledger.record', text: '买肥料'),
      throwsA(isA<UnsupportedApiException>()),
    );
  });
}
