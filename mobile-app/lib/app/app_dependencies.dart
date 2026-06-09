import '../data/api/api_client.dart';
import '../data/repositories/auth_repository.dart';
import '../data/repositories/billing_repository.dart';
import '../data/repositories/dashboard_repository.dart';
import '../data/repositories/profile_repository.dart';
import '../data/repositories/workbench_repository.dart';
import '../data/repositories/yaya_repository.dart';
import '../data/session/app_session.dart';
import '../data/session/session_store.dart';

abstract class AppDependencies {
  Future<void> login({required String phone, required String password});

  Future<void> register({
    required String phone,
    required String password,
    required String nickname,
  });

  Future<void> loadAppOverview();
}

class BackendAppDependencies implements AppDependencies {
  BackendAppDependencies({ApiClient? client}) : this._(client ?? ApiClient());

  BackendAppDependencies._(this.client)
      : auth = AuthRepository(client),
        session = AppSession(
          client: client,
          store: const SecureSessionStore(),
        ),
        profile = ProfileRepository(client),
        dashboard = DashboardRepository(client),
        billing = BillingRepository(client),
        workbench = WorkbenchRepository(client),
        yaya = YayaRepository(client);

  final ApiClient client;
  final AuthRepository auth;
  final AppSession session;
  final ProfileRepository profile;
  final DashboardRepository dashboard;
  final BillingRepository billing;
  final WorkbenchRepository workbench;
  final YayaRepository yaya;

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
}
