import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/billing_repository.dart';
import 'package:farm_manager_app/data/repositories/workbench_repository.dart';
import 'package:farm_manager_app/features/record_flow/record_flow_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  RecordFlowController controllerFor(RecordingAdapter adapter) {
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:9876/api/v2'));
    dio.httpClientAdapter = adapter;
    final client = ApiClient(dio: dio);
    return RecordFlowController(
      workbench: WorkbenchRepository(client),
      billing: BillingRepository(client),
    );
  }

  test('独立智能帮填缺少后端接口时明确返回不可用', () async {
    final adapter = RecordingAdapter({});
    await expectLater(controllerFor(adapter).parse('今天买肥料 200'),
        throwsA(isA<UnsupportedApiException>()));
    expect(adapter.requests, isEmpty);
  });

  test('成本场景保存到 costs', () async {
    final adapter =
        RecordingAdapter({'POST /cost-records': costRecordResponse});
    final controller = controllerFor(adapter);

    final result = await controller.save(
      const RecordDraft(
        scene: 'ledger.record',
        originalText: '买肥料 200',
        fields: {'amount': 200, 'category': '肥料', 'record_type': 'cost'},
        missingFields: [],
        warnings: [],
      ),
    );

    expect(result.label, '已同步到账本');
    expect(adapter.find('POST', '/cost-records').data, {
      'amount': 200,
      'category': '肥料',
      'record_type': 'cost',
    });
  });

  test('赊账、农事、作业单和工资场景保存到对应接口', () async {
    final adapter = RecordingAdapter({
      'POST /debts': costRecordResponse,
      'POST /farm-logs': logResponse,
      'POST /work-orders': workOrderResponse,
      'POST /labor/wages': wageResponse,
    });
    final controller = controllerFor(adapter);

    await controller.save(
      const RecordDraft(
        scene: 'debt.record',
        originalText: '',
        fields: {'amount': 200},
        missingFields: [],
        warnings: [],
      ),
    );
    await controller.save(
      const RecordDraft(
        scene: 'farm.log',
        originalText: '',
        fields: {'operation_type': '浇水'},
        missingFields: [],
        warnings: [],
      ),
    );
    await controller.save(
      const RecordDraft(
        scene: 'work_order.create',
        originalText: '',
        fields: {'operation_type': '浇水'},
        missingFields: [],
        warnings: [],
      ),
    );
    await controller.save(
      const RecordDraft(
        scene: 'labor.wage',
        originalText: '',
        fields: {'worker_id': 4},
        missingFields: [],
        warnings: [],
      ),
    );

    expect(adapter.find('POST', '/debts').data, {'amount': 200});
    expect(adapter.find('POST', '/farm-logs').data, {'operation_type': '浇水'});
    expect(adapter.find('POST', '/work-orders').data, {
      'operation_type': '浇水',
    });
    expect(adapter.find('POST', '/labor/wages').data, {'worker_id': 4});
  });

  test('缺字段和未知场景不会伪造保存目标', () async {
    final controller = controllerFor(RecordingAdapter({}));

    expect(
      () => controller.save(
        const RecordDraft(
          scene: 'ledger.record',
          originalText: '买肥料',
          fields: {},
          missingFields: ['amount'],
          warnings: [],
        ),
      ),
      throwsA(isA<MissingRecordFieldsException>()),
    );
    expect(
      () => controller.save(
        const RecordDraft(
          scene: 'unknown',
          originalText: '随便记一下',
          fields: {},
          missingFields: [],
          warnings: [],
        ),
      ),
      throwsA(isA<UnsupportedRecordSceneException>()),
    );
  });
}
