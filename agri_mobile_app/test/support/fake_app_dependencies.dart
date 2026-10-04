import 'package:dio/dio.dart';
import 'package:farm_manager_app/app/app_dependencies.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/business_repository.dart';
import 'package:farm_manager_app/data/repositories/dashboard_repository.dart';
import 'package:farm_manager_app/data/repositories/location_repository.dart';
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
        v2WeatherResponse,
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
    LocationRepository? locations,
    LocationService? location,
  })  : profile = profile ?? _fakeProfileRepository(),
        dashboard = dashboard ?? _fakeDashboardRepository(),
        billing = billing ?? _fakeBillingRepository(),
        business = business ?? _fakeBusinessRepository(),
        workbench = workbench ?? _fakeWorkbenchRepository(),
        yaya = yaya ?? _fakeYayaRepository(),
        locations = locations ?? _fakeLocationRepository(),
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
  final LocationRepository locations;
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
    '/crop-cycles': paginatedCyclesResponse,
    'POST /crop-cycles': cycleResponse,
    '/crop-templates': paginatedCropTemplatesResponse,
    'POST /crop-templates': cropTemplateResponse,
    '/workers/summary': paginatedWorkerSummariesResponse,
    'POST /workers': workerResponse,
    'POST /labor/wages': wageResponse,
    'POST /work-orders': workOrderResponse,
    'POST /cost-records': costRecordResponse,
    '/cost-categories': {'items': [categoryResponse]},
    '/smart-fill/parse': smartFillParseResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
  dio.httpClientAdapter = adapter;
  return BusinessRepository(ApiClient(dio: dio));
}

ProfileRepository _fakeProfileRepository() {
  final adapter = RecordingAdapter({
    '/users/me': userResponse,
    '/users/me/settings': settingsResponse,
    '/api/app/version': versionResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
  dio.httpClientAdapter = adapter;
  return ProfileRepository(ApiClient(dio: dio));
}

YayaRepository _fakeYayaRepository() {
  final adapter = RecordingAdapter({
    '/conversations': [conversationResponse],
    '/conversations/s1': [messageResponse],
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
  dio.httpClientAdapter = adapter;
  return YayaRepository(ApiClient(dio: dio));
}

LocationRepository _fakeLocationRepository() {
  final adapter = RecordingAdapter({
    '/locations/search': {
      'items': [
        {
          'display_name': '苏州市虎丘区',
          'lat': 31.3296,
          'lon': 120.4342,
        },
      ],
    },
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
  dio.httpClientAdapter = adapter;
  return LocationRepository(ApiClient(dio: dio));
}

DashboardRepository _fakeDashboardRepository() {
  final adapter = RecordingAdapter({
    '/dashboard': {'pending_work_orders': 1},
    '/users/me/settings': settingsResponse,
    '/weather': v2WeatherResponse,
    '/work-orders': paginatedWorkOrdersResponse,
    '/labor/unsettled-summary': unsettledLaborSummaryResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
  dio.httpClientAdapter = adapter;
  return DashboardRepository(ApiClient(dio: dio));
}

BillingRepository _fakeBillingRepository() {
  final adapter = RecordingAdapter({
    '/cost-records': paginatedCostsResponse,
    'POST /cost-records': costRecordResponse,
    '/cost-records/summary/yearly': yearlySummaryResponse,
    '/debts': debtsResponse,
    'POST /debts': costRecordResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
  dio.httpClientAdapter = adapter;
  return BillingRepository(ApiClient(dio: dio));
}

WorkbenchRepository _fakeWorkbenchRepository() {
  final adapter = RecordingAdapter({
    '/crop-cycles': {'items': [], 'total': 0},
    '/planting-units': {'items': []},
    '/workers': {'items': []},
    '/farm-logs/operations/types': {'items': []},
    '/work-orders': paginatedWorkOrdersResponse,
    'POST /work-orders': workOrderResponse,
    '/farm-logs': paginatedLogsResponse,
    'POST /farm-logs': logResponse,
    'POST /labor/wages': wageResponse,
    '/smart-fill/scenarios': smartFillScenariosResponse,
    '/smart-fill/parse': smartFillParseResponse,
  });
  final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
  dio.httpClientAdapter = adapter;
  return WorkbenchRepository(ApiClient(dio: dio));
}
