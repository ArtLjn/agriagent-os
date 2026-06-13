import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/features/profile/profile_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart'
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
      currentVersionCode: 3,
    );

    final model = await controller.load();

    expect(model.nickname, '农友');
    expect(model.phone, '13800138000');
    expect(model.role, '用户');
    expect(model.status, '正常');
    expect(model.city, '睢宁县');
    expect(model.assistantRoleLabel, '温暖陪伴型');
    expect(model.latestVersion, '0.1.0');
    expect(model.hasVersionUpdate, isTrue);
    expect(model.updateSummary, '更新至 v0.1.0');
    expect(model.versionLabel, '发现新版本 0.1.0');
    expect(model.versionStatus, '可更新');
    expect(model.versionChangelog, '更新');
    expect(model.versionDownloadUrl, 'https://example.test/app.apk');
    expect(adapter.find('GET', '/api/app/version').query, {
      'current_version_code': 3,
    });
  });

  test('版本接口返回 null 字段时不会触发红屏类型错误', () async {
    final adapter = RecordingAdapter({
      '/auth/me': userResponse,
      '/settings': settingsResponse,
      '/api/app/version': {
        'latest_version': null,
        'latest_version_code': null,
        'download_url': null,
        'changelog': null,
        'force_update': null,
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = ProfileController(
      repository: ProfileRepository(ApiClient(dio: dio)),
      currentVersionCode: 3,
    );

    final model = await controller.load();

    expect(model.versionLabel, '版本未知');
    expect(model.versionStatus, '已是最新');
    expect(model.versionChangelog, '暂无更新说明');
    expect(model.versionDownloadUrl, '暂无下载地址');
    expect(model.hasVersionUpdate, isFalse);
    expect(model.updateSummary, '当前已是最新版本');
  });

  test('版本接口 force_update 不映射为强制更新文案', () async {
    final adapter = RecordingAdapter({
      '/auth/me': userResponse,
      '/settings': settingsResponse,
      '/api/app/version': {
        'latest_version': '1.2.7',
        'latest_version_code': 9,
        'download_url': 'https://example.test/app.apk',
        'changelog': '更新至 v1.2.7',
        'force_update': true,
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = ProfileController(
      repository: ProfileRepository(ApiClient(dio: dio)),
      currentVersionCode: 3,
    );

    final model = await controller.load();

    expect(model.hasVersionUpdate, isTrue);
    expect(model.versionLabel, '发现新版本 1.2.7');
    expect(model.versionStatus, '可更新');
    expect(model.updateSummary, '更新至 v1.2.7');
  });

  test('农场地区缺失时兼容使用 settings.defaultCity', () async {
    final adapter = RecordingAdapter({
      '/auth/me': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': null,
        },
      },
      '/settings': settingsResponse,
      '/api/app/version': versionResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
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
      'PUT /auth/me/farm-location': {
        ...userResponse,
        'farm': {
          'id': 1,
          'name': '农友的农场',
          'location': '邳州市',
        },
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final repository = ProfileRepository(ApiClient(dio: dio));

    final user = await repository.updateFarmLocation(
      location: '邳州市',
      farmId: 1,
    );

    final request = adapter.find('PUT', '/auth/me/farm-location');
    expect(request.data, {'location': '邳州市', 'farm_id': 1});
    expect(user.farm?.location, '邳州市');
  });

  test('默认使用运行时构建号检查版本，最新版不提示更新', () async {
    final adapter = RecordingAdapter({
      '/auth/me': userResponse,
      '/settings': settingsResponse,
      '/api/app/version': {
        'latest_version': '1.2.7',
        'latest_version_code': 13,
        'download_url': 'https://example.test/app.apk',
        'changelog': '更新至 v1.2.7',
        'force_update': false,
      },
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = ProfileController(
      repository: ProfileRepository(ApiClient(dio: dio)),
      currentVersionCodeResolver: () async => 13,
    );

    final model = await controller.load();

    expect(model.hasVersionUpdate, isFalse);
    expect(model.versionLabel, '已是最新 1.2.7');
    expect(model.versionStatus, '已是最新');
    expect(model.updateSummary, '当前已是最新版本');
    expect(adapter.find('GET', '/api/app/version').query, {
      'current_version_code': 13,
    });
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
    expect(model.updateSummary, '当前已是最新版本');
  });
}
