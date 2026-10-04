import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/features/profile/profile_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart'
    show RecordingAdapter, settingsResponse, userResponse;

void main() {
  test('加载个人资料、设置和版本并映射为页面模型', () async {
    final adapter = RecordingAdapter({
      '/users/me': userResponse,
      '/users/me/settings': settingsResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final controller = ProfileController(
      repository: ProfileRepository(ApiClient(dio: dio)),
      currentVersionCode: 3,
    );

    final model = await controller.load();

    expect(model.nickname, '农友');
    expect(model.phone, '13800138000');
    expect(model.role, '用户');
    expect(model.status, '正常');
    expect(model.city, '睢宁县');
    expect(model.assistantRoleLabel, '温暖陪伴型');
    expect(model.hasVersionUpdate, isFalse);
    expect(model.versionStatus, '暂不可用');
    expect(adapter.requests.map((request) => request.path),
        ['/users/me', '/users/me/settings']);
  });

  test('农场地区缺失时兼容使用 settings.defaultCity', () async {
    final adapter = RecordingAdapter({
      '/users/me': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': null,
        },
      },
      '/users/me/settings': settingsResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final controller = ProfileController(
      repository: ProfileRepository(ApiClient(dio: dio)),
      currentVersionCode: 3,
    );

    final model = await controller.load();

    expect(model.city, '寿光');
  });

  test('仓库更新经营地区时调用 farm-location 接口', () async {
    final adapter = RecordingAdapter({
      '/users/me': userResponse,
      'PATCH /farms/1/location': {'id': 1, 'name': '农友的农场', 'location': '邳州市'},
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final repository = ProfileRepository(ApiClient(dio: dio));

    final user = await repository.updateFarmLocation(
      location: '邳州市',
      farmId: 1,
    );

    final request = adapter.find('PATCH', '/farms/1/location');
    expect(request.data, {'location': '邳州市'});
    expect(user.farm?.location, '邳州市');
  });

  test('版本展示字段缺失时模型提供安全兜底文案', () {
    final model = ProfileViewModel(
      nickname: '农友',
      phone: '13800138000',
      role: '用户',
      status: '正常',
      city: '寿光',
      assistantRoleLabel: '温暖陪伴型',
      versionLabel: null as dynamic,
      versionStatus: null as dynamic,
      versionChangelog: null as dynamic,
      versionDownloadUrl: null as dynamic,
    );

    expect(model.safeVersionLabel, '版本未知');
    expect(model.safeVersionStatus, '已是最新');
    expect(model.safeVersionChangelog, '暂无更新说明');
    expect(model.safeVersionDownloadUrl, '暂无下载地址');
    expect(model.safeLatestVersion, '未知版本');
    expect(model.updateSummary, '暂无更新说明');
  });
}
