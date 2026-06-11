import '../api/api_client.dart';
import '../api/api_models.dart';

class BusinessRepository {
  BusinessRepository(this.client);

  final ApiClient client;

  Future<ApiRecord> createLedgerRecord(Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.postMap('/costs', data: data));
  }

  Future<PageResult<ApiRecord>> listCycles(
      {int page = 1, int size = 20}) async {
    final data = await client.getMap('/cycles', query: {
      'page': page,
      'size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> saveCycle(
    Map<String, Object?> data, {
    int? cycleId,
  }) async {
    final response = cycleId == null
        ? await client.postMap('/cycles', data: data)
        : await client.putMap('/cycles/$cycleId', data: data);
    return ApiRecord.fromJson(response);
  }

  Future<PageResult<ApiRecord>> listCropTemplates({
    int page = 1,
    int size = 20,
  }) async {
    final data = await client.getMap('/crops/templates', query: {
      'page': page,
      'size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> saveCropTemplate(
    Map<String, Object?> data, {
    int? templateId,
  }) async {
    final response = templateId == null
        ? await client.postMap('/crops/templates', data: data)
        : await client.putMap('/crops/templates/$templateId', data: data);
    return ApiRecord.fromJson(response);
  }

  Future<PageResult<ApiRecord>> listWorkerSummaries({
    bool activeOnly = false,
  }) async {
    final data = await client.getMap('/planting/workers/summary', query: {
      'active_only': activeOnly,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> saveWorker(
    Map<String, Object?> data, {
    int? workerId,
  }) async {
    final response = workerId == null
        ? await client.postMap('/planting/workers', data: data)
        : await client.putMap('/planting/workers/$workerId', data: data);
    return ApiRecord.fromJson(response);
  }

  Future<ApiRecord> createWage(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/planting/labor/wages', data: data),
    );
  }

  Future<ApiRecord> createWorkOrder(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/planting/work-orders', data: data),
    );
  }

  Future<SmartFillResult> parseSmartFill({
    required String scene,
    required String text,
    Map<String, Object?> context = const {},
  }) async {
    final data = await client.postMap('/smart-fill/parse', data: {
      'scene': scene,
      'text': text,
      'context': context,
    });
    return SmartFillResult.fromJson(data);
  }
}
