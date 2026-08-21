import '../api/api_client.dart';
import '../api/api_models.dart';

class WorkbenchRepository {
  WorkbenchRepository(this.client);

  final ApiClient client;

  Future<PageResult<ApiRecord>> listCycles(
      {int page = 1, int size = 20}) async {
    final data = await client.getMap(
      '/crop-cycles',
      query: {'page': page, 'page_size': size},
    );
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> createCycle(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/crop-cycles', data: data),
    );
  }

  Future<ApiRecord> getCycle(int cycleId) async {
    return ApiRecord.fromJson(await client.getMap('/crop-cycles/$cycleId'));
  }

  Future<ApiRecord> updateCycle(int cycleId, Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.patchMap('/crop-cycles/$cycleId', data: data),
    );
  }

  Future<ApiRecord> advanceCycleStage(int cycleId) async {
    return ApiRecord.fromJson(
      await client.postMap('/crop-cycles/$cycleId/advance-stage'),
    );
  }

  Future<Map<String, dynamic>> parseCycle(String description) {
    throw const UnsupportedApiException('v2 暂不提供茬口智能解析接口');
  }

  Future<List<ApiRecord>> listPlantingUnits({int? cycleId}) async {
    final data = await client.getItems('/planting-units', query: {
      'cycle_id': cycleId,
    });
    return _records(data);
  }

  Future<ApiRecord> createPlantingUnit(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/planting-units', data: data),
    );
  }

  Future<ApiRecord> updatePlantingUnit(
    int unitId,
    Map<String, Object?> data,
  ) async {
    return ApiRecord.fromJson(
      await client.patchMap('/planting-units/$unitId', data: data),
    );
  }

  Future<List<ApiRecord>> listWorkers({bool activeOnly = false}) async {
    final data = await client.getItems('/workers', query: {
      'active_only': activeOnly,
    });
    return _records(data);
  }

  Future<ApiRecord> createWorker(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/workers', data: data),
    );
  }

  Future<PageResult<ApiRecord>> listWorkerSummaries({
    bool activeOnly = false,
  }) async {
    final data = await client.getMap('/workers/summary', query: {
      'active_only': activeOnly,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> updateWorker(
      int workerId, Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.patchMap('/workers/$workerId', data: data),
    );
  }

  Future<List<ApiRecord>> listOperationTypes({String? cropName}) async {
    final data = await client.getItems('/farm-logs/operations/types', query: {
      'crop_name': cropName,
    });
    return _records(data);
  }

  Future<ApiRecord> saveWage(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/labor/wages', data: data),
    );
  }

  Future<ApiRecord> updateWage(
      int laborEntryId, Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.patchMap('/labor/wages/$laborEntryId', data: data),
    );
  }

  Future<PageResult<ApiRecord>> listWorkOrders({
    int? cycleId,
    int page = 1,
    int size = 20,
  }) async {
    final data = await client.getMap('/work-orders', query: {
      'cycle_id': cycleId,
      'page': page,
      'page_size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> createWorkOrder(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/work-orders', data: data),
    );
  }

  Future<ApiRecord> getWorkOrder(int workOrderId) async {
    return ApiRecord.fromJson(
      await client.getMap('/work-orders/$workOrderId'),
    );
  }

  Future<List<ApiRecord>> listRecentOperations({
    int? cycleId,
    int days = 30,
    int limit = 20,
  }) async {
    final data = await client.getItems('/recent-operations', query: {
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
    final data = await client.getMap('/farm-logs', query: {
      'cycle_id': cycleId,
      'operation_type': operationType,
      'page': page,
      'page_size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> createLog(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/farm-logs', data: data),
    );
  }

  Future<ApiRecord> updateLog(int logId, Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.patchMap('/farm-logs/$logId', data: data),
    );
  }

  Future<List<ApiRecord>> listSmartFillScenarios() async {
    throw const UnsupportedApiException('v2 暂不提供智能帮填场景接口');
  }

  Future<SmartFillResult> parseSmartFill({
    required String scene,
    required String text,
    Map<String, Object?> context = const {},
    String? idempotencyKey,
  }) async {
    throw const UnsupportedApiException('v2 暂不提供智能帮填接口');
  }

  Future<void> warmUp() async {
    await Future.wait([
      client.get('/crop-cycles'),
      client.get('/planting-units'),
      client.get('/workers'),
      client.get('/farm-logs/operations/types'),
      client.get('/farm-logs'),
    ]);
  }

  List<ApiRecord> _records(List<dynamic> data) {
    return data
        .map((item) =>
            ApiRecord.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
  }
}
