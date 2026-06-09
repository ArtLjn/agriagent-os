import '../api/api_client.dart';
import '../api/api_models.dart';
import '../repositories/auth_repository.dart';
import 'session_store.dart';

class AppSession {
  AppSession({
    required this.client,
    required this.store,
    AuthRepository? auth,
  }) : auth = auth ?? AuthRepository(client);

  final ApiClient client;
  final SessionStore store;
  final AuthRepository auth;

  Future<bool> restore() async {
    final token = await store.readToken();
    client.setAccessToken(token);
    return token != null && token.isNotEmpty;
  }

  Future<AuthSession> login({
    required String phone,
    required String password,
  }) async {
    final session = await auth.login(phone: phone, password: password);
    await store.writeToken(session.token);
    client.setAccessToken(session.token);
    return session;
  }

  Future<AuthSession> register({
    required String phone,
    required String password,
    required String nickname,
  }) async {
    final session = await auth.register(
      phone: phone,
      password: password,
      nickname: nickname,
    );
    await store.writeToken(session.token);
    client.setAccessToken(session.token);
    return session;
  }

  Future<void> logout() async {
    await store.clearToken();
    client.setAccessToken(null);
  }
}
