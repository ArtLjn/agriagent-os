import '../api/api_client.dart';
import '../api/api_models.dart';

class ProfileRepository {
  ProfileRepository(this.client);

  final ApiClient client;

  Future<AppUser> getProfile() async {
    return AppUser.fromJson(await client.getMap('/users/me'));
  }

  Future<AppUser> updateProfile(Map<String, Object?> data) async {
    return AppUser.fromJson(await client.patchMap('/users/me', data: data));
  }

  Future<UserSettings> getSettings() async {
    return UserSettings.fromJson(await client.getMap('/users/me/settings'));
  }

  Future<UserSettings> updateSettings(Map<String, Object?> data) async {
    return UserSettings.fromJson(
      await client.patchMap('/users/me/settings', data: data),
    );
  }

  Future<AppUser> updateFarmLocation({
    required String location,
    double? latitude,
    double? longitude,
    int? farmId,
  }) async {
    final current = await getProfile();
    final resolvedFarmId = farmId ?? current.farm?.id;
    if (resolvedFarmId == null || resolvedFarmId <= 0) {
      throw StateError('当前用户没有可更新的农场');
    }
    final farm = await client.patchMap(
      '/farms/$resolvedFarmId/location',
      data: {
        'location': location,
        if (latitude != null) 'lat': latitude,
        if (longitude != null) 'lon': longitude,
      },
    );
    return AppUser(
      id: current.id,
      phone: current.phone,
      nickname: current.nickname,
      role: current.role,
      status: current.status,
      avatarUrl: current.avatarUrl,
      createdAt: current.createdAt,
      farm: FarmProfile.fromJson(farm),
    );
  }

  Future<VersionInfo> checkVersion({int currentVersionCode = 0}) async {
    // v2 暂未提供移动端版本服务，返回不可用状态，避免请求旧入口。
    return const VersionInfo.unavailable();
  }

  Future<void> loadProfile() async {
    await Future.wait([
      client.get('/users/me'),
      client.get('/users/me/settings'),
    ]);
  }
}
