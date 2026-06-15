import 'package:dio/dio.dart';
import 'package:farm_manager_app/app/app_dependencies.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/business_repository.dart';
import 'package:farm_manager_app/data/repositories/dashboard_repository.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/data/repositories/workbench_repository.dart';
import 'package:farm_manager_app/data/repositories/yaya_repository.dart';
import 'package:farm_manager_app/data/location/location_service.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'api_test_fixtures.dart'
    show
        RecordingAdapter,
        conversationResponse,
        costRecordResponse,
        categoryResponse,
        dailyAdviceResponse,
        debtsResponse,
        logResponse,
        messageResponse,
        paginatedCostsResponse,
        paginatedCropTemplatesResponse,
        paginatedCyclesResponse,
        paginatedLogsResponse,
        paginatedWorkOrdersResponse,
        paginatedWorkerSummariesResponse,
        settingsResponse,
        smartFillParseResponse,
        smartFillScenariosResponse,
        unsettledLaborSummaryResponse,
        userResponse,
        versionResponse,
        wageResponse,
        weatherResponse,
        cropTemplateResponse,
        cycleResponse,
        workerResponse,
        workOrderResponse,
        yearlySummaryResponse;

void setMockAppPackageInfo({
  String version = '1.2.7',
  String buildNumber = '13',
}) {
  PackageInfo.setMockInitialValues(
    appName: '田掌柜',
    packageName: 'com.farmmanager.farm_manager_app',
    version: version,
    buildNumber: buildNumber,
    buildSignature: '',
  );
}

class FakeAppDependencies implements AppDependencies {
  FakeAppDependencies({
    this.restoreResult = false,
    this.loginError,
    this.registerError,
    ProfileRepository? profile,
    DashboardRepository? dashboard,
    BillingRepository? billing,
    BusinessRepository? business,
    WorkbenchRepository? workbench,
    YayaRepository? yaya,
    LocationService? location,
  })  : profile = profile ?? _fakeProfileRepository(),
        dashboard = dashboard ?? _fakeDashboardRepository(),
        billing = billing ?? _fakeBillingRepository(),
        business = business ?? _fakeBusinessRepository(),
        workbench = workbench ?? _fakeWorkbenchRepository(),
        yaya = yaya ?? _fakeYayaRepository(),
        location = location ?? FakeLocationService() {
    setMockAppPackageInfo();
  }

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

class FakeLocationService implements LocationService {
  FakeLocationService({this.suggestion});

  FarmLocationSuggestion? suggestion;
  int requestCalls = 0;

  @override
  Future<FarmLocationSuggestion?> requestCurrentFarmLocation() async {
    requestCalls += 1;
    return suggestion;
  }
}

BusinessRepository _fakeBusinessRepository() {
  final adapter = RecordingAdapter({
    '/cycles': paginatedCyclesResponse,
    'POST /cycles': cycleResponse,
    '/crops/templates': paginatedCropTemplatesResponse,
    'POST /crops/templates': cropTemplateResponse,
    '/planting/workers/summary': paginatedWorkerSummariesResponse,
    'POST /planting/workers': workerResponse,
    'POST /planting/labor/wages': wageResponse,
    'POST /planting/work-orders': workOrderResponse,
    'POST /costs': costRecordResponse,
    '/cost-categories': [categoryResponse],
    '/smart-fill/parse': smartFillParseResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
  dio.httpClientAdapter = adapter;
  return BusinessRepository(ApiClient(dio: dio));
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

DashboardRepository _fakeDashboardRepository() {
  final adapter = RecordingAdapter({
    '/agent/daily': dailyAdviceResponse,
    '/settings': settingsResponse,
    '/weather/forecast': weatherResponse,
    '/planting/work-orders': paginatedWorkOrdersResponse,
    '/planting/labor/unsettled-summary': unsettledLaborSummaryResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
  dio.httpClientAdapter = adapter;
  return DashboardRepository(ApiClient(dio: dio));
}

BillingRepository _fakeBillingRepository() {
  final adapter = RecordingAdapter({
    '/costs': paginatedCostsResponse,
    'POST /costs': costRecordResponse,
    '/costs/summary/2026': yearlySummaryResponse,
    '/debts': debtsResponse,
    'POST /debts': costRecordResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
  dio.httpClientAdapter = adapter;
  return BillingRepository(ApiClient(dio: dio));
}

WorkbenchRepository _fakeWorkbenchRepository() {
  final adapter = RecordingAdapter({
    '/cycles': {'items': [], 'total': 0},
    '/planting/units': [],
    '/planting/workers': [],
    '/planting/operation-types': [],
    '/planting/work-orders': paginatedWorkOrdersResponse,
    'POST /planting/work-orders': workOrderResponse,
    '/logs': paginatedLogsResponse,
    'POST /logs': logResponse,
    'POST /planting/labor/wages': wageResponse,
    '/smart-fill/scenarios': smartFillScenariosResponse,
    '/smart-fill/parse': smartFillParseResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
  dio.httpClientAdapter = adapter;
  return WorkbenchRepository(ApiClient(dio: dio));
}
