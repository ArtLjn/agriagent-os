import '../api/api_client.dart';
import '../api/api_models.dart';

class AuthRepository {
  AuthRepository(this.client);

  final ApiClient client;

  Future<AuthSession> login({
    required String phone,
    required String password,
  }) async {
    final data = await client.postMap('/auth/login', data: {
      'phone': phone,
      'password': password,
    });
    final session = AuthSession.fromJson(data);
    client.setAccessToken(session.token);
    return session;
  }

  Future<AuthSession> register({
    required String phone,
    required String password,
    String nickname = '农友',
  }) async {
    final data = await client.postMap('/auth/register', data: {
      'phone': phone,
      'password': password,
      'nickname': nickname,
    });
    final session = AuthSession.fromJson(data);
    client.setAccessToken(session.token);
    return session;
  }
}
