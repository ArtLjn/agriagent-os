import 'package:dio/dio.dart';
import 'package:farm_manager_app/app/app_dependencies.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';

import '../data/repositories/app_api_integration_test.dart'
    show RecordingAdapter, settingsResponse, userResponse, versionResponse;

class FakeAppDependencies implements AppDependencies {
  FakeAppDependencies({
    this.restoreResult = false,
    this.loginError,
    this.registerError,
    ProfileRepository? profile,
  }) : profile = profile ?? _fakeProfileRepository();

  @override
  final ProfileRepository profile;
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
