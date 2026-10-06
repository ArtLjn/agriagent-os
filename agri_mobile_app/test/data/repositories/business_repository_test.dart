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
      '/crop-cycles': paginatedCyclesResponse,
      'POST /crop-cycles': cycleResponse,
      'PATCH /crop-cycles/7': cycleResponse,
      'DELETE /crop-cycles/7': {'message': 'ok'},
      '/crop-templates': paginatedCropTemplatesResponse,
      'POST /crop-templates': cropTemplateResponse,
      'PATCH /crop-templates/3': cropTemplateResponse,
      'DELETE /crop-templates/3': {'message': 'ok'},
      '/workers/summary': paginatedWorkerSummariesResponse,
      'POST /workers': workerResponse,
      'PATCH /workers/5': workerResponse,
      'DELETE /workers/5': {'message': 'ok'},
      'POST /labor/wages': wageResponse,
      'POST /farm-logs': logResponse,
      'POST /work-orders': workOrderResponse,
      'POST /cost-records': costRecordResponse,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    repository = BusinessRepository(ApiClient(dio: dio));
  });

  test('记账保存映射到 POST /cost-records', () async {
    await repository.createLedgerRecord({
      'record_type': 'cost',
      'category': '种子',
      'amount': 128,
      'record_date': '2026-06-10',
    });

    final request = adapter.find('POST', '/cost-records');
    expect(request.data, containsPair('record_type', 'cost'));
    expect(request.data, containsPair('category', '种子'));
  });

  test('茬口列表与保存接口映射正确', () async {
    await repository.listCycles();
    await repository.saveCycle({'name': '春茬番茄'});
    await repository.saveCycle({'name': '春茬番茄'}, cycleId: 7);
    await repository.deleteCycle(7);

    expect(adapter.find('GET', '/crop-cycles').query, containsPair('page', 1));
    expect(adapter.find('POST', '/crop-cycles').data,
        containsPair('name', '春茬番茄'));
    expect(adapter.find('PATCH', '/crop-cycles/7').data,
        containsPair('name', '春茬番茄'));
    expect(adapter.find('DELETE', '/crop-cycles/7').path, '/crop-cycles/7');
  });

  test('作物模板接口映射正确', () async {
    await repository.listCropTemplates();
    await repository.saveCropTemplate({'name': '西瓜', 'stages': []});
    await repository
        .saveCropTemplate({'name': '西瓜', 'stages': []}, templateId: 3);
    await repository.deleteCropTemplate(3);

    expect(
        adapter.find('GET', '/crop-templates').query, containsPair('page', 1));
    expect(adapter.find('POST', '/crop-templates').data,
        containsPair('name', '西瓜'));
    expect(adapter.find('PATCH', '/crop-templates/3').data,
        containsPair('name', '西瓜'));
    expect(
      adapter.find('DELETE', '/crop-templates/3').path,
      '/crop-templates/3',
    );
  });

  test('工人、工资和农事作业接口映射正确', () async {
    await repository.listWorkerSummaries();
    await repository.saveWorker({'name': '老王'});
    await repository.saveWorker({'name': '老王'}, workerId: 5);
    await repository.deleteWorker(5);
    await repository.createWage({'worker_name': '老王'});
    await repository.createWorkOrder({'operation_type': '浇水'});

    expect(adapter.find('GET', '/workers/summary').query,
        containsPair('active_only', false));
    expect(adapter.find('POST', '/workers').data, containsPair('name', '老王'));
    expect(
        adapter.find('PATCH', '/workers/5').data, containsPair('name', '老王'));
    expect(
      adapter.find('DELETE', '/workers/5').path,
      '/workers/5',
    );
    expect(adapter.find('POST', '/labor/wages').data,
        containsPair('worker_name', '老王'));
    expect(adapter.find('POST', '/work-orders').data,
        containsPair('operation_type', '浇水'));
  });

  test('农事记录接口映射到 POST /farm-logs', () async {
    await repository.createFarmLog({
      'cycle_id': 7,
      'operation_type': '浇水',
      'operation_date': '2026-06-10',
    });

    final request = adapter.find('POST', '/farm-logs');
    expect(request.data, containsPair('cycle_id', 7));
    expect(request.data, containsPair('operation_type', '浇水'));
  });
}
