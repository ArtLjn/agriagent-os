import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/business_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  late RecordingAdapter adapter;
  late BusinessRepository repository;

  setUp(() {
    adapter = RecordingAdapter({
      '/cycles': paginatedCyclesResponse,
      'POST /cycles': cycleResponse,
      'PUT /cycles/7': cycleResponse,
      '/crops/templates': paginatedCropTemplatesResponse,
      'POST /crops/templates': cropTemplateResponse,
      'PUT /crops/templates/3': cropTemplateResponse,
      '/planting/workers/summary': paginatedWorkerSummariesResponse,
      'POST /planting/workers': workerResponse,
      'PUT /planting/workers/5': workerResponse,
      'POST /planting/labor/wages': wageResponse,
      'POST /logs': logResponse,
      'POST /planting/work-orders': workOrderResponse,
      'POST /costs': costRecordResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    repository = BusinessRepository(ApiClient(dio: dio));
  });

  test('记账保存映射到 POST /costs', () async {
    await repository.createLedgerRecord({
      'record_type': 'cost',
      'category': '种子',
      'amount': 128,
      'record_date': '2026-06-10',
    });

    final request = adapter.find('POST', '/costs');
    expect(request.data, containsPair('record_type', 'cost'));
    expect(request.data, containsPair('category', '种子'));
  });

  test('茬口列表与保存接口映射正确', () async {
    await repository.listCycles();
    await repository.saveCycle({'name': '春茬番茄'});
    await repository.saveCycle({'name': '春茬番茄'}, cycleId: 7);

    expect(adapter.find('GET', '/cycles').query, containsPair('page', 1));
    expect(adapter.find('POST', '/cycles').data, containsPair('name', '春茬番茄'));
    expect(adapter.find('PUT', '/cycles/7').data, containsPair('name', '春茬番茄'));
  });

  test('作物模板接口映射正确', () async {
    await repository.listCropTemplates();
    await repository.saveCropTemplate({'name': '西瓜', 'stages': []});
    await repository
        .saveCropTemplate({'name': '西瓜', 'stages': []}, templateId: 3);

    expect(
        adapter.find('GET', '/crops/templates').query, containsPair('page', 1));
    expect(adapter.find('POST', '/crops/templates').data,
        containsPair('name', '西瓜'));
    expect(adapter.find('PUT', '/crops/templates/3').data,
        containsPair('name', '西瓜'));
  });

  test('工人、工资和农事作业接口映射正确', () async {
    await repository.listWorkerSummaries();
    await repository.saveWorker({'name': '老王'});
    await repository.saveWorker({'name': '老王'}, workerId: 5);
    await repository.createWage({'worker_name': '老王'});
    await repository.createWorkOrder({'operation_type': '浇水'});

    expect(adapter.find('GET', '/planting/workers/summary').query,
        containsPair('active_only', false));
    expect(adapter.find('POST', '/planting/workers').data,
        containsPair('name', '老王'));
    expect(adapter.find('PUT', '/planting/workers/5').data,
        containsPair('name', '老王'));
    expect(adapter.find('POST', '/planting/labor/wages').data,
        containsPair('worker_name', '老王'));
    expect(adapter.find('POST', '/planting/work-orders').data,
        containsPair('operation_type', '浇水'));
  });

  test('农事记录接口映射到 POST /logs', () async {
    await repository.createFarmLog({
      'cycle_id': 7,
      'operation_type': '浇水',
      'operation_date': '2026-06-10',
    });

    final request = adapter.find('POST', '/logs');
    expect(request.data, containsPair('cycle_id', 7));
    expect(request.data, containsPair('operation_type', '浇水'));
  });
}
