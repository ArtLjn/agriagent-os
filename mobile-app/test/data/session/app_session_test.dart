import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/session/app_session.dart';
import 'package:farm_manager_app/data/session/session_store.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart'
    show RecordingAdapter, tokenResponse;

void main() {
  test('登录成功后保存 token 并写入 Authorization header', () async {
    final store = MemorySessionStore();
    final adapter = RecordingAdapter({'/auth/login': tokenResponse});
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final client = ApiClient(dio: dio);
    final session = AppSession(client: client, store: store);

    await session.login(phone: '13800138000', password: 'password');

    expect(await store.readToken(), 'token-1');
    expect(client.dio.options.headers['Authorization'], 'Bearer token-1');
  });

  test('登录保存 token 失败时不会写入 Authorization header', () async {
    final store = FailingSessionStore();
    final adapter = RecordingAdapter({'/auth/login': tokenResponse});
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final client = ApiClient(dio: dio);
    final session = AppSession(client: client, store: store);

    await expectLater(
      session.login(phone: '13800138000', password: 'password'),
      throwsStateError,
    );

    expect(client.dio.options.headers.containsKey('Authorization'), false);
  });

  test('启动恢复 token 后可直接带鉴权请求', () async {
    final store = MemorySessionStore(initialToken: 'restored-token');
    final client = ApiClient(
      dio: Dio(BaseOptions(baseUrl: 'http://localhost:8099')),
    );
    final session = AppSession(client: client, store: store);

    final restored = await session.restore();

    expect(restored, true);
    expect(
        client.dio.options.headers['Authorization'], 'Bearer restored-token');
  });

  test('退出登录会清除本地 token 和请求头', () async {
    final store = MemorySessionStore(initialToken: 'token-1');
    final client = ApiClient(
      dio: Dio(BaseOptions(baseUrl: 'http://localhost:8099')),
    )..setAccessToken('token-1');
    final session = AppSession(client: client, store: store);

    await session.logout();

    expect(await store.readToken(), isNull);
    expect(client.dio.options.headers.containsKey('Authorization'), false);
  });
}

class FailingSessionStore implements SessionStore {
  @override
  Future<String?> readToken() async => null;

  @override
  Future<void> writeToken(String token) async {
    throw StateError('token 写入失败');
  }

  @override
  Future<void> clearToken() async {}
}
