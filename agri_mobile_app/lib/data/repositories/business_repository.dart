import '../api/api_client.dart';
import '../api/api_models.dart';

class BusinessRepository {
  BusinessRepository(this.client);

  final ApiClient client;

  Future<ApiRecord> createLedgerRecord(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/cost-records', data: data),
    );
  }

  Future<PageResult<ApiRecord>> listCostCategories({
    int page = 1,
    int size = 100,
  }) async {
    final data = await client.getItems('/cost-categories');
    final records = data
        .map((item) =>
            ApiRecord.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
    return PageResult(
      items: records,
      total: records.length,
    );
  }

  Future<ApiRecord> createCostCategory(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/cost-categories', data: data),
    );
  }

  Future<void> deleteCostCategory(int categoryId) async {
    await client.delete('/cost-categories/$categoryId');
  }

  Future<PageResult<ApiRecord>> listCycles(
      {int page = 1, int size = 20}) async {
    final data = await client.getMap('/crop-cycles', query: {
      'page': page,
      'page_size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<PageResult<ApiRecord>> listAllCycles() async {
    return PageResult.fromJson(
        await client.getAllPages('/crop-cycles'), ApiRecord.fromJson);
  }

  Future<PageResult<ApiRecord>> listAllCropTemplates() async {
    return PageResult.fromJson(
        await client.getAllPages('/crop-templates'), ApiRecord.fromJson);
  }

  Future<ApiRecord> saveCycle(
    Map<String, Object?> data, {
    int? cycleId,
  }) async {
    final response = cycleId == null
        ? await client.postMap('/crop-cycles', data: data)
        : await client.patchMap('/crop-cycles/$cycleId', data: data);
    return ApiRecord.fromJson(response);
  }

  Future<ApiRecord> createPlantingUnit(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
        await client.postMap('/planting-units', data: data));
  }

  Future<void> deleteCycle(int cycleId) async {
    await client.delete('/crop-cycles/$cycleId');
  }

  Future<PageResult<ApiRecord>> listCropTemplates({
    int page = 1,
    int size = 20,
  }) async {
    final data = await client.getMap('/crop-templates', query: {
      'page': page,
      'page_size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> saveCropTemplate(
    Map<String, Object?> data, {
    int? templateId,
  }) async {
    final response = templateId == null
        ? await client.postMap('/crop-templates', data: data)
        : await client.patchMap('/crop-templates/$templateId', data: data);
    return ApiRecord.fromJson(response);
  }

  Future<void> deleteCropTemplate(int templateId) async {
    await client.delete('/crop-templates/$templateId');
  }

  Future<PageResult<ApiRecord>> listWorkerSummaries({
    bool activeOnly = false,
  }) async {
    final data = await client.getMap('/workers/summary', query: {
      'active_only': activeOnly,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> saveWorker(
    Map<String, Object?> data, {
    int? workerId,
  }) async {
    final response = workerId == null
        ? await client.postMap('/workers', data: data)
        : await client.patchMap('/workers/$workerId', data: data);
    return ApiRecord.fromJson(response);
  }

  Future<void> deleteWorker(int workerId) async {
    await client.delete('/workers/$workerId');
  }

  Future<ApiRecord> createWage(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/labor/wages', data: data),
    );
  }

  Future<ApiRecord> createFarmLog(Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.postMap('/farm-logs', data: data));
  }

  Future<ApiRecord> createWorkOrder(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/work-orders', data: data),
    );
  }

  Future<SmartFillResult> parseSmartFill({
    required String scene,
    required String text,
    Map<String, Object?> context = const {},
  }) async {
    throw const UnsupportedApiException('v2 暂不提供智能帮填接口');
  }
}
