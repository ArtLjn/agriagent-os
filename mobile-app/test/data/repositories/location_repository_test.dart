import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/location_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  test('位置仓库从 /locations/search 获取统一坐标', () async {
    final adapter = RecordingAdapter({
      '/locations/search': {
        'items': [
          {
            'display_name': '苏州市虎丘区',
            'lat': 31.3296,
            'lon': 120.4342,
            'coordinate_source': 'manual_verified',
          },
        ],
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final repository = LocationRepository(ApiClient(dio: dio));

    final result = await repository.searchLocations('虎丘');

    expect(adapter.find('GET', '/locations/search').query, {
      'q': '虎丘',
      'limit': 20,
    });
    expect(result.single.name, '苏州市虎丘区');
    expect(result.single.latitude, 31.3296);
    expect(result.single.longitude, 120.4342);
  });
}
