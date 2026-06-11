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
      '/auth/me': userResponse,
      'PUT /auth/me': userResponse,
      '/settings': settingsResponse,
      'PUT /settings': settingsResponse,
      '/api/app/version': versionResponse,
      '/agent/chat': {'reply': '收到'},
      '/agent/conversations': [conversationResponse],
      '/agent/conversations/s1/messages': [messageResponse],
      '/agent/daily': dailyAdviceResponse,
      '/agent/daily/refresh': dailyAdviceResponse,
      '/agent/report': reportResponse,
      '/agent/advice-history': [adviceHistoryResponse],
      '/agent/report-history': [reportHistoryResponse],
      '/agent/reports': paginatedReportsResponse,
      '/costs': paginatedCostsResponse,
      'POST /costs': costRecordResponse,
      '/costs/summary/2026': yearlySummaryResponse,
      '/costs/cycles/7/profit': cycleProfitResponse,
      '/costs/parse': costParseResponse,
      '/cost-categories': [categoryResponse],
      'POST /cost-categories': categoryResponse,
      '/debts': debtsResponse,
      'POST /debts': costRecordResponse,
      '/debts/settle': costRecordResponse,
      '/weather/forecast': weatherResponse,
      '/cycles': paginatedCyclesResponse,
      'POST /cycles': cycleResponse,
      '/cycles/7': cycleResponse,
      '/cycles/7/advance-stage': cycleResponse,
      '/cycles/parse': cycleParseResponse,
      '/planting/units': [plantingUnitResponse],
      'POST /planting/units': plantingUnitResponse,
      '/planting/units/3': plantingUnitResponse,
      '/planting/workers': [workerResponse],
      'POST /planting/workers': workerResponse,
      '/planting/workers/summary': paginatedWorkersResponse,
      '/planting/workers/4': workerResponse,
      '/planting/operation-types': [operationTypeResponse],
      '/planting/labor/wages': wageResponse,
      '/planting/labor/wages/5': wageResponse,
      '/planting/work-orders': paginatedWorkOrdersResponse,
      'POST /planting/work-orders': workOrderResponse,
      '/planting/work-orders/9': workOrderResponse,
      '/planting/recent-operations': [recentOperationResponse],
      '/planting/labor/unsettled-summary': unsettledLaborSummaryResponse,
      '/logs': paginatedLogsResponse,
      'POST /logs': logResponse,
      '/logs/11': logResponse,
      '/smart-fill/scenarios': smartFillScenariosResponse,
      '/smart-fill/parse': smartFillParseResponse,
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
    await profile.getSettings();
    await profile.updateSettings({'default_city': '寿光'});
    await profile.checkVersion(currentVersionCode: 3);
    await yaya.sendMessage('今天浇水吗', cycleId: 7, sessionId: 's1');
    await yaya.loadConversations(limit: 10);
    await yaya.loadMessages('s1');
    await dashboard.getDailyAdvice(cycleId: 7);
    await dashboard.refreshDailyAdvice(cycleId: 7);
    await dashboard.createReport(cycleId: 7, reportType: 'weekly');
    await dashboard.listAdviceHistory(cycleId: 7);
    await dashboard.listReportHistory(cycleId: 7);
    await dashboard.listReports(page: 2, size: 5);
    await dashboard.getForecast(days: 3, location: '寿光');
    await dashboard.getUnsettledLaborSummary();
    await billing.listCosts(page: 2, size: 10, cycleId: 7);
    await billing.createCost({'record_type': 'cost'});
    await billing.getYearlySummary(2026);
    await billing.getCycleProfit(7);
    await billing.parseCost('买肥料 200');
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
    await workbench.parseCycle('春季种番茄');
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
    await workbench.listSmartFillScenarios();
    await workbench.parseSmartFill(
      scene: 'ledger.record',
      text: '买肥料 200',
      context: {'cycle_id': 7},
      idempotencyKey: 'req-1',
    );

    expect(
      adapter.find('GET', '/auth/me').headers['Authorization'],
      'Bearer token-1',
    );
    expect(adapter.find('POST', '/agent/chat').data, {
      'cycle_id': 7,
      'message': '今天浇水吗',
      'session_id': 's1',
    });
    expect(adapter.find('GET', '/weather/forecast').query, {
      'days': 3,
      'location': '寿光',
      'lat': 34.20442,
      'lon': 117.28386,
    });
    expect(adapter.find('GET', '/costs').query, {
      'cycle_id': 7,
      'page': 2,
      'size': 10,
    });
    expect(
        adapter.find('POST', '/smart-fill/parse').headers['X-Idempotency-Key'],
        'req-1');
    expect(adapter.find('POST', '/smart-fill/parse').data, {
      'scene': 'ledger.record',
      'text': '买肥料 200',
      'context': {'cycle_id': 7},
    });
  });

  test('芽芽流式接口解析 SSE content、skills 和 done', () async {
    final adapter = StreamingAdapter();
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final yaya = YayaRepository(ApiClient(dio: dio));

    final events = await yaya.streamMessage('今天浇水吗', sessionId: 's1').toList();

    expect(events.map((event) => event.content).whereType<String>(), [
      '建议',
      '傍晚浇水',
    ]);
    expect(events.any((event) => event.done), true);
    expect(events.any((event) => event.skills.contains('weather')), true);
    expect(adapter.requests.single.path, '/agent/chat/stream');
    expect(adapter.requests.single.data, {
      'message': '今天浇水吗',
      'session_id': 's1',
    });
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
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
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
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
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
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final yaya = YayaRepository(ApiClient(dio: dio));

    final events = await yaya.streamMessage('今天浇水吗').toList();

    expect(events.first.error, '芽芽回复解析失败，请稍后重试');
    expect(events.last.done, true);
  });
}
