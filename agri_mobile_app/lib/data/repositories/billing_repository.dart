import '../api/api_client.dart';
import '../api/api_models.dart';

class BillingRepository {
  BillingRepository(this.client);

  final ApiClient client;

  Future<PageResult<ApiRecord>> listCosts({
    int? cycleId,
    String? category,
    String? sourceType,
    int? sourceId,
    int page = 1,
    int size = 20,
  }) async {
    final data = await client.getMap('/cost-records', query: {
      'cycle_id': cycleId,
      'category': category,
      'source_type': sourceType,
      'source_id': sourceId,
      'page': page,
      'page_size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<PageResult<ApiRecord>> listAllCosts() async {
    final data = await client.getAllPages('/cost-records');
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> createCost(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
      await client.postMap('/cost-records', data: data),
    );
  }

  Future<Map<String, dynamic>> getYearlySummary(int year) {
    return client.getMap('/cost-records/summary/yearly', query: {'year': year});
  }

  Future<Map<String, dynamic>> getCycleProfit(int cycleId) {
    return client.getMap('/cost-records/cycles/$cycleId/profit');
  }

  Future<Map<String, dynamic>> parseCost(String description) {
    throw const UnsupportedApiException('v2 暂不提供智能记账解析接口');
  }

  Future<List<ApiRecord>> listCategories() async {
    final data = await client.getItems('/cost-categories');
    return _records(data);
  }

  Future<ApiRecord> createCategory(Map<String, Object?> data) async {
    return ApiRecord.fromJson(
        await client.postMap('/cost-categories', data: data));
  }

  Future<Map<String, dynamic>> listDebts({
    String? counterparty,
    int page = 1,
    int size = 20,
  }) {
    return client.getMap('/debts', query: {
      'counterparty': counterparty,
      'page': page,
      'page_size': size,
    });
  }

  Future<ApiRecord> createDebt(Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.postMap('/debts', data: data));
  }

  Future<ApiRecord> settleDebt({
    required String counterparty,
    Object? amount,
    String? note,
  }) async {
    return ApiRecord.fromJson(await client.postMap('/debts/settle',
        data: {
          'counterparty': counterparty,
          'amount': amount,
          'note': note,
        }..removeWhere((_, value) => value == null)));
  }

  Future<void> loadBillingSummary() async {
    await Future.wait([
      client.get('/cost-records'),
      client.get('/cost-records/summary/yearly', query: {'year': 2026}),
      client.get('/debts'),
    ]);
  }

  List<ApiRecord> _records(List<dynamic> data) {
    return data
        .map((item) =>
            ApiRecord.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
  }
}
