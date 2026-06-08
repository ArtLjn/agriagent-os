import '../api/api_client.dart';
import '../api/api_models.dart';

class WorkbenchRepository {
  WorkbenchRepository(this.client);

  final ApiClient client;

  Future<PageResult<ApiRecord>> listCycles({int page = 1, int size = 20}) async {
    final data = await client.getMap('/cycles', query: {'page': page, 'size': size});
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> createCycle(Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.postMap('/cycles', data: data));
  }

  Future<ApiRecord> getCycle(int cycleId) async {
    return ApiRecord.fromJson(await client.getMap('/cycles/$cycleId'));
  }

  Future<ApiRecord> updateCycle(int cycleId, Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.putMap('/cycles/$cycleId', data: data));
  }

  Future<ApiRecord> advanceCycleStage(int cycleId) async {
    return ApiRecord.fromJson(await client.postMap('/cycles/$cycleId/advance-stage'));
  }

  Future<Map<String, dynamic>> parseCycle(String description) {
    return client.postMap('/cycles/parse', data: {'description': description});
  }

  Future<List<ApiRecord>> listPlantingUnits({int? cycleId}) async {
    final data = await client.getList('/planting/units', query: {
      'cycle_id': cycleId,
    });
    return _records(data);
  }

  Future<ApiRecord> createPlantingUnit(Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.postMap('/planting/units', data: data));
  }

  Future<ApiRecord> updatePlantingUnit(
    int unitId,
    Map<String, Object?> data,
  ) async {
    return ApiRecord.fromJson(
      await client.putMap('/planting/units/$unitId', data: data),
    );
  }

  Future<List<ApiRecord>> listWorkers({bool activeOnly = false}) async {
    final data = await client.getList('/planting/workers', query: {
      'active_only': activeOnly,
    });
    return _records(data);
  }

  Future<ApiRecord> createWorker(Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.postMap('/planting/workers', data: data));
  }

  Future<PageResult<ApiRecord>> listWorkerSummaries({
    bool activeOnly = false,
  }) async {
    final data = await client.getMap('/planting/workers/summary', query: {
      'active_only': activeOnly,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> updateWorker(int workerId, Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.putMap('/planting/workers/$workerId', data: data),
    );
  }

  Future<List<ApiRecord>> listOperationTypes({String? cropName}) async {
    final data = await client.getList('/planting/operation-types', query: {
      'crop_name': cropName,
    });
    return _records(data);
  }

  Future<ApiRecord> saveWage(Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.postMap('/planting/labor/wages', data: data));
  }

  Future<ApiRecord> updateWage(int laborEntryId, Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.patchMap('/planting/labor/wages/$laborEntryId', data: data),
    );
  }

  Future<PageResult<ApiRecord>> listWorkOrders({
    int? cycleId,
    int page = 1,
    int size = 20,
  }) async {
    final data = await client.getMap('/planting/work-orders', query: {
      'cycle_id': cycleId,
      'page': page,
      'size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> createWorkOrder(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/planting/work-orders', data: data),
    );
  }

  Future<ApiRecord> getWorkOrder(int workOrderId) async {
    return ApiRecord.fromJson(
      await client.getMap('/planting/work-orders/$workOrderId'),
    );
  }

  Future<List<ApiRecord>> listRecentOperations({
    int? cycleId,
    int days = 30,
    int limit = 20,
  }) async {
    final data = await client.getList('/planting/recent-operations', query: {
      'cycle_id': cycleId,
      'days': days,
      'limit': limit,
    });
    return _records(data);
  }

  Future<PageResult<ApiRecord>> listLogs({
    int? cycleId,
    String? operationType,
    int page = 1,
    int size = 20,
  }) async {
    final data = await client.getMap('/logs', query: {
      'cycle_id': cycleId,
      'operation_type': operationType,
      'page': page,
      'size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> createLog(Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.postMap('/logs', data: data));
  }

  Future<ApiRecord> updateLog(int logId, Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.putMap('/logs/$logId', data: data));
  }

  Future<List<ApiRecord>> listSmartFillScenarios() async {
    final data = await client.getMap('/smart-fill/scenarios');
    return _records(data['items'] as List<dynamic>? ?? []);
  }

  Future<SmartFillResult> parseSmartFill({
    required String scene,
    required String text,
    Map<String, Object?> context = const {},
    String? idempotencyKey,
  }) async {
    final data = await client.postMap(
      '/smart-fill/parse',
      data: {
        'scene': scene,
        'text': text,
        'context': context,
      },
      headers: idempotencyKey == null ? null : {'X-Idempotency-Key': idempotencyKey},
    );
    return SmartFillResult.fromJson(data);
  }

  Future<void> warmUp() async {
    await Future.wait([
      client.get('/cycles'),
      client.get('/planting/units'),
      client.get('/planting/workers'),
      client.get('/planting/operation-types'),
      client.get('/logs'),
    ]);
  }

  List<ApiRecord> _records(List<dynamic> data) {
    return data
        .map((item) => ApiRecord.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
  }
}
