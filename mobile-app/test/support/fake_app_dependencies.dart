import 'package:farm_manager_app/app/app_dependencies.dart';

class FakeAppDependencies implements AppDependencies {
  FakeAppDependencies({
    this.restoreResult = false,
    this.loginError,
    this.registerError,
  });

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
