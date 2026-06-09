import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/features/profile/profile_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../data/repositories/app_api_integration_test.dart'
    show RecordingAdapter, settingsResponse, userResponse, versionResponse;

void main() {
  test('加载个人资料、设置和版本并映射为页面模型', () async {
    final adapter = RecordingAdapter({
      '/auth/me': userResponse,
      '/settings': settingsResponse,
      '/api/app/version': versionResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = ProfileController(
      repository: ProfileRepository(ApiClient(dio: dio)),
    );

    final model = await controller.load();

    expect(model.nickname, '农友');
    expect(model.phone, '13800138000');
    expect(model.city, '寿光');
    expect(model.weatherCity, '寿光');
    expect(model.versionLabel, '版本 0.1.0');
  });
}
