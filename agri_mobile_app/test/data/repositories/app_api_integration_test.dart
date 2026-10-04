import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/auth_repository.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/dashboard_repository.dart';
import 'package:farm_manager_app/data/repositories/profile_repository.dart';
import 'package:farm_manager_app/data/repositories/workbench_repository.dart';
import 'package:farm_manager_app/data/repositories/yaya_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  test('仓库方法集成后端 app API 路径、query 与 body', () async {
    final adapter = RecordingAdapter({
      '/auth/login': tokenResponse,
      '/auth/register': tokenResponse,
      '/users/me': userResponse,
      'PATCH /users/me': userResponse,
      'PATCH /farms/1/location': {'id': 1, 'name': '农友的农场', 'location': '邳州市'},
      '/users/me/settings': settingsResponse,
      'PATCH /users/me/settings': settingsResponse,
      '/conversations': [conversationResponse],
      '/conversations/s1/messages': {
        'items': [messageResponse]
      },
      '/dashboard': {'cycles': [], 'recent_logs': []},
      '/cost-records': paginatedCostsResponse,
      'POST /cost-records': costRecordResponse,
      '/cost-records/summary/yearly': yearlySummaryResponse,
      '/cost-records/cycles/7/profit': cycleProfitResponse,
      '/cost-categories': {
        'items': [categoryResponse]
      },
      'POST /cost-categories': categoryResponse,
      '/debts': debtsResponse,
      'POST /debts': costRecordResponse,
      '/debts/settle': costRecordResponse,
      '/weather': weatherResponse,
      '/crop-cycles': paginatedCyclesResponse,
      'POST /crop-cycles': cycleResponse,
      '/crop-cycles/7': cycleResponse,
      '/crop-cycles/7/advance-stage': cycleResponse,
      '/planting-units': {
        'items': [plantingUnitResponse]
      },
      'POST /planting-units': plantingUnitResponse,
      '/planting-units/3': plantingUnitResponse,
      '/workers': {
        'items': [workerResponse]
      },
      'POST /workers': workerResponse,
      '/workers/summary': paginatedWorkersResponse,
      '/workers/4': workerResponse,
      '/farm-logs/operations/types': {
        'items': [operationTypeResponse]
      },
      '/labor/wages': wageResponse,
      '/labor/wages/5': wageResponse,
      '/work-orders': paginatedWorkOrdersResponse,
      'POST /work-orders': workOrderResponse,
      '/work-orders/9': workOrderResponse,
      '/recent-operations': {
        'items': [recentOperationResponse]
      },
      '/labor/unsettled-summary': unsettledLaborSummaryResponse,
      '/farm-logs': paginatedLogsResponse,
      'POST /farm-logs': logResponse,
      '/farm-logs/11': logResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'https://api.example.test'));
    dio.httpClientAdapter = adapter;
    final client = ApiClient(dio: dio)..setAccessToken('token-1');

    final auth = AuthRepository(client);
    final profile = ProfileRepository(client);
    final yaya = YayaRepository(client);
    final dashboard = DashboardRepository(client);
    final billing = BillingRepository(client);
    final workbench = WorkbenchRepository(client);

    client.setAccessToken(null);
    expect((await auth.login(phone: '13800138000', password: 'password')).token,
        'token-1');
    expect(
      client.dio.options.headers.containsKey('Authorization'),
      false,
    );
    client.setAccessToken('token-1');
    await auth.register(
      phone: '13800138000',
      password: 'password',
      nickname: '农友',
    );
    await profile.getProfile();
    await profile.updateProfile({'nickname': '新昵称'});
    final updatedUser = await profile.updateFarmLocation(location: '邳州市');
    await profile.getSettings();
    await profile.updateSettings({'default_city': '寿光'});
    await profile.checkVersion(currentVersionCode: 3);
    await expectLater(yaya.sendMessage('今天浇水吗', cycleId: 7, sessionId: 's1'),
        throwsA(isA<UnsupportedApiException>()));
    await yaya.loadConversations(limit: 10);
    await yaya.loadMessages('s1');
    await expectLater(
        yaya.loadSkills(), throwsA(isA<UnsupportedApiException>()));
    await dashboard.getDailyAdvice(cycleId: 7);
    await expectLater(dashboard.refreshDailyAdvice(cycleId: 7),
        throwsA(isA<UnsupportedApiException>()));
    await expectLater(dashboard.createReport(cycleId: 7, reportType: 'weekly'),
        throwsA(isA<UnsupportedApiException>()));
    await expectLater(dashboard.listAdviceHistory(cycleId: 7),
        throwsA(isA<UnsupportedApiException>()));
    await expectLater(dashboard.listReportHistory(cycleId: 7),
        throwsA(isA<UnsupportedApiException>()));
    await expectLater(dashboard.listReports(page: 2, size: 5),
        throwsA(isA<UnsupportedApiException>()));
    await dashboard.getForecast(days: 3, location: '寿光');
    await dashboard.getUnsettledLaborSummary();
    await billing.listCosts(page: 2, size: 10, cycleId: 7);
    await billing.createCost({'record_type': 'cost'});
    await billing.getYearlySummary(2026);
    await billing.getCycleProfit(7);
    await expectLater(() => billing.parseCost('买肥料 200'),
        throwsA(isA<UnsupportedApiException>()));
    await billing.listCategories();
    await billing
        .createCategory({'name': '肥料', 'type': 'cost', 'icon': 'leaf'});
    await billing.listDebts(counterparty: '老王');
    await billing.createDebt({'record_type': 'cost'});
    await billing.settleDebt(counterparty: '老王', amount: '200');
    await workbench.listCycles(page: 1, size: 20);
    await workbench.createCycle({'name': '春茬'});
    await workbench.getCycle(7);
    await workbench.updateCycle(7, {'name': '夏茬'});
    await workbench.advanceCycleStage(7);
    await expectLater(() => workbench.parseCycle('春季种番茄'),
        throwsA(isA<UnsupportedApiException>()));
    await workbench.listPlantingUnits(cycleId: 7);
    await workbench.createPlantingUnit({'cycle_id': 7, 'name': 'A棚'});
    await workbench.updatePlantingUnit(3, {'name': 'B棚'});
    await workbench.listWorkers(activeOnly: true);
    await workbench.createWorker({'name': '张三'});
    await workbench.listWorkerSummaries(activeOnly: true);
    await workbench.updateWorker(4, {'name': '李四'});
    await workbench.listOperationTypes(cropName: '西瓜');
    await workbench.saveWage({'cycle_id': 7});
    await workbench.updateWage(5, {'paid_amount': '100'});
    await workbench.listWorkOrders(cycleId: 7);
    await workbench.createWorkOrder({'operation_type': '浇水'});
    await workbench.getWorkOrder(9);
    await workbench.listRecentOperations(cycleId: 7, days: 7, limit: 3);
    await workbench.listLogs(cycleId: 7, operationType: '浇水');
    await workbench.createLog({'cycle_id': 7});
    await workbench.updateLog(11, {'note': '已处理'});
    await expectLater(workbench.listSmartFillScenarios(),
        throwsA(isA<UnsupportedApiException>()));
    await expectLater(
        workbench.parseSmartFill(scene: 'ledger.record', text: '买肥料 200'),
        throwsA(isA<UnsupportedApiException>()));

    expect(
      adapter.requests
          .where((request) =>
              request.method == 'GET' && request.path == '/users/me')
          .first
          .headers['Authorization'],
      'Bearer token-1',
    );
    expect(updatedUser.farm?.location, '邳州市');
    expect(adapter.find('PATCH', '/farms/1/location').data, {
      'location': '邳州市',
    });
    expect(adapter.find('GET', '/weather').query, {
      'days': 3,
      'location': '寿光',
    });
    expect(adapter.find('GET', '/cost-records').query, {
      'cycle_id': 7,
      'page': 2,
      'page_size': 10,
    });
  });

  test('芽芽流式接口解析 SSE content、skills 和 done', () async {
    final adapter = StreamingAdapter();
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final yaya = YayaRepository(ApiClient(dio: dio));

    final events = await yaya.streamMessage('今天浇水吗', sessionId: 's1').toList();

    expect(events.map((event) => event.content).whereType<String>(), [
      '建议',
      '傍晚浇水',
    ]);
    expect(events.any((event) => event.done), true);
    expect(events.any((event) => event.skills.contains('weather')), true);
    expect(adapter.requests.single.path, '/chat');
    expect(adapter.requests.single.data, containsPair('message', '今天浇水吗'));
    expect(adapter.requests.single.data, containsPair('conversation_id', 's1'));
    expect((adapter.requests.single.data as Map)['client_request_id'],
        startsWith('mobile-'));
    expect(adapter.requests.single.headers['Accept'], 'text/event-stream');
  });

  test('芽芽流式接口按 SSE 空行聚合同一事件的多行 data', () async {
    final adapter = StreamingAdapter(
      [
        'data: {"content":"建议",\n',
        'data: "skills":["weather"]}\n\n',
        'data: [DONE]\n\n',
      ].join(),
    );
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final yaya = YayaRepository(ApiClient(dio: dio));

    final events = await yaya.streamMessage('今天浇水吗').toList();

    expect(events.first.content, '建议');
    expect(events.first.skills, ['weather']);
    expect(events.last.done, true);
  });

  test('芽芽流式接口兼容 type/data pending_action 事件', () async {
    final adapter = StreamingAdapter(
      [
        'data: {"type":"pending_action","data":{"action_id":"a1","skill_name":"create_crop_cycle","params":{"作物":"大豆"}}}\n\n',
        'data: [DONE]\n\n',
      ].join(),
    );
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final yaya = YayaRepository(ApiClient(dio: dio));

    final events = await yaya.streamMessage('我想种大豆').toList();

    expect(events.first.pendingAction?['action_id'], 'a1');
    expect(events.first.pendingAction?['params'], {'作物': '大豆'});
  });

  test('芽芽流式接口遇到 malformed JSON 会产出解析错误事件', () async {
    final adapter = StreamingAdapter(
      [
        'data: {"content":\n\n',
        'data: [DONE]\n\n',
      ].join(),
    );
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final yaya = YayaRepository(ApiClient(dio: dio));

    final events = await yaya.streamMessage('今天浇水吗').toList();

    expect(events.first.error, '芽芽回复解析失败，请稍后重试');
    expect(events.last.done, true);
  });
}
