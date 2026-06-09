import 'package:farm_manager_app/app/app_dependencies.dart';

class FakeAppDependencies implements AppDependencies {
  FakeAppDependencies({
    this.loginError,
    this.registerError,
  });

  final Object? loginError;
  final Object? registerError;
  int loginCalls = 0;
  int registerCalls = 0;
  int overviewLoads = 0;
  String? lastPhone;
  String? lastPassword;
  String? lastNickname;

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
}
