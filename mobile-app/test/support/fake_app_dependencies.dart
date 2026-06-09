import 'package:dio/dio.dart';
import 'package:farm_manager_app/app/app_dependencies.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/data/repositories/yaya_repository.dart';

import 'api_test_fixtures.dart'
    show
        RecordingAdapter,
        conversationResponse,
        messageResponse,
        settingsResponse,
        userResponse,
        versionResponse;

class FakeAppDependencies implements AppDependencies {
  FakeAppDependencies({
    this.restoreResult = false,
    this.loginError,
    this.registerError,
    ProfileRepository? profile,
    YayaRepository? yaya,
  })  : profile = profile ?? _fakeProfileRepository(),
        yaya = yaya ?? _fakeYayaRepository();

  @override
  final ProfileRepository profile;
  @override
  final YayaRepository yaya;
  final bool restoreResult;
  final Object? loginError;
  final Object? registerError;
  int restoreCalls = 0;
  int loginCalls = 0;
  int registerCalls = 0;
  int logoutCalls = 0;
  int overviewLoads = 0;
  String? lastPhone;
  String? lastPassword;
  String? lastNickname;

  @override
  Future<bool> restoreSession() async {
    restoreCalls += 1;
    return restoreResult;
  }

  @override
  Future<void> login({required String phone, required String password}) async {
    loginCalls += 1;
    lastPhone = phone;
    lastPassword = password;
    if (loginError != null) throw loginError!;
  }

  @override
  Future<void> register({
    required String phone,
    required String password,
    required String nickname,
  }) async {
    registerCalls += 1;
    lastPhone = phone;
    lastPassword = password;
    lastNickname = nickname;
    if (registerError != null) throw registerError!;
  }

  @override
  Future<void> loadAppOverview() async {
    overviewLoads += 1;
  }

  @override
  Future<void> logout() async {
    logoutCalls += 1;
  }
}

ProfileRepository _fakeProfileRepository() {
  final adapter = RecordingAdapter({
    '/auth/me': userResponse,
    '/settings': settingsResponse,
    '/api/app/version': versionResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
  dio.httpClientAdapter = adapter;
  return ProfileRepository(ApiClient(dio: dio));
}

YayaRepository _fakeYayaRepository() {
  final adapter = RecordingAdapter({
    '/agent/conversations': [conversationResponse],
    '/agent/conversations/s1/messages': [messageResponse],
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
  dio.httpClientAdapter = adapter;
  return YayaRepository(ApiClient(dio: dio));
}
