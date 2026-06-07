import '../api/api_client.dart';

class ProfileRepository {
  ProfileRepository(this.client);

  final ApiClient client;

  Future<void> loadProfile() async {
    await Future.wait([
      client.get('/auth/me'),
      client.get('/settings'),
      client.get('/api/app/version'),
    ]);
  }
}
