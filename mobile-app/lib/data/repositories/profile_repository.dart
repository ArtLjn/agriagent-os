import '../api/api_client.dart';
import '../api/api_models.dart';

class ProfileRepository {
  ProfileRepository(this.client);

  final ApiClient client;

  Future<AppUser> getProfile() async {
    return AppUser.fromJson(await client.getMap('/auth/me'));
  }

  Future<AppUser> updateProfile(Map<String, Object?> data) async {
    return AppUser.fromJson(await client.putMap('/auth/me', data: data));
  }

  Future<UserSettings> getSettings() async {
    return UserSettings.fromJson(await client.getMap('/settings'));
  }

  Future<UserSettings> updateSettings(Map<String, Object?> data) async {
    return UserSettings.fromJson(await client.putMap('/settings', data: data));
  }

  Future<VersionInfo> checkVersion({int currentVersionCode = 0}) async {
    final data = await client.getMap(
      '/api/app/version',
      query: {'current_version_code': currentVersionCode},
    );
    return VersionInfo.fromJson(data);
  }

  Future<void> loadProfile() async {
    await Future.wait([
      client.get('/auth/me'),
      client.get('/settings'),
      client.get('/api/app/version'),
    ]);
  }
}
