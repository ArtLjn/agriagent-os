import '../data/api/api_client.dart';
import '../data/location/location_service.dart';
import '../data/location/system_location_service.dart';
import '../data/repositories/billing_repository.dart';
import '../data/repositories/business_repository.dart';
import '../data/repositories/dashboard_repository.dart';
import '../data/repositories/profile_repository.dart';
import '../data/repositories/workbench_repository.dart';
import '../data/repositories/yaya_repository.dart';
import '../data/session/app_session.dart';
import '../data/session/session_store.dart';

abstract class AppDependencies {
  ProfileRepository get profile;

  DashboardRepository get dashboard;

  BillingRepository get billing;

  WorkbenchRepository get workbench;

  BusinessRepository get business;

  YayaRepository get yaya;

  LocationService get location;

  Future<bool> restoreSession();

  Future<void> login({required String phone, required String password});

  Future<void> register({
    required String phone,
    required String password,
    required String nickname,
  });

  Future<void> loadAppOverview();

  Future<void> logout();
}

class BackendAppDependencies implements AppDependencies {
  BackendAppDependencies({ApiClient? client}) : this._(client ?? ApiClient());

  BackendAppDependencies._(this.client)
      : session = AppSession(
          client: client,
          store: const SecureSessionStore(),
        ),
        profile = ProfileRepository(client),
        dashboard = DashboardRepository(client),
        billing = BillingRepository(client),
        business = BusinessRepository(client),
        workbench = WorkbenchRepository(client),
        yaya = YayaRepository(client),
        location = SystemLocationService();

  final ApiClient client;
  final AppSession session;
  @override
  final ProfileRepository profile;
  @override
  final DashboardRepository dashboard;
  @override
  final BillingRepository billing;
  @override
  final BusinessRepository business;
  @override
  final WorkbenchRepository workbench;
  @override
  final YayaRepository yaya;
  @override
  final LocationService location;

  @override
  Future<bool> restoreSession() {
    return session.restore();
  }

  @override
  Future<void> login({required String phone, required String password}) async {
    await session.login(phone: phone, password: password);
  }

  @override
  Future<void> register({
    required String phone,
    required String password,
    required String nickname,
  }) async {
    await session.register(
      phone: phone,
      password: password,
      nickname: nickname,
    );
  }

  @override
  Future<void> loadAppOverview() async {
    await Future.wait([
      profile.getProfile(),
      dashboard.loadOverview(),
      billing.loadBillingSummary(),
      workbench.warmUp(),
      yaya.loadConversations(),
    ]);
  }

  @override
  Future<void> logout() {
    return session.logout();
  }
}
