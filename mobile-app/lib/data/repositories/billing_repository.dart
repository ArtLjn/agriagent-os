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
    final data = await client.getMap('/costs', query: {
      'cycle_id': cycleId,
      'category': category,
      'source_type': sourceType,
      'source_id': sourceId,
      'page': page,
      'size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<ApiRecord> createCost(Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.postMap('/costs', data: data));
  }

  Future<Map<String, dynamic>> getYearlySummary(int year) {
    return client.getMap('/costs/summary/$year');
  }

  Future<Map<String, dynamic>> getCycleProfit(int cycleId) {
    return client.getMap('/costs/cycles/$cycleId/profit');
  }

  Future<Map<String, dynamic>> parseCost(String description) {
    return client.postMap('/costs/parse', data: {'description': description});
  }

  Future<List<ApiRecord>> listCategories() async {
    final data = await client.getList('/cost-categories');
    return _records(data);
  }

  Future<ApiRecord> createCategory(Map<String, Object?> data) async {
    return ApiRecord.fromJson(await client.postMap('/cost-categories', data: data));
  }

  Future<Map<String, dynamic>> listDebts({
    String? counterparty,
    int page = 1,
    int size = 20,
  }) {
    return client.getMap('/debts', query: {
      'counterparty': counterparty,
      'page': page,
      'size': size,
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
    return ApiRecord.fromJson(await client.postMap('/debts/settle', data: {
      'counterparty': counterparty,
      'amount': amount,
      'note': note,
    }..removeWhere((_, value) => value == null)));
  }

  Future<void> loadBillingSummary() async {
    await Future.wait([
      client.get('/costs'),
      client.get('/costs/summary/2026'),
      client.get('/debts'),
    ]);
  }

  List<ApiRecord> _records(List<dynamic> data) {
    return data
        .map((item) => ApiRecord.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
  }
}
