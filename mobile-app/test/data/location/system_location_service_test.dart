import 'package:farm_manager_app/data/location/system_location_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('最近城市匹配返回支持的经营地区', () {
    final city = nearestSupportedCity(
      latitude: 34.31,
      longitude: 117.96,
    );

    expect(city, '邳州市');
  });

  test('距离支持城市过远时不自动猜测经营地区', () {
    final city = nearestSupportedCity(
      latitude: 0,
      longitude: 0,
    );

    expect(city, isNull);
  });
}
