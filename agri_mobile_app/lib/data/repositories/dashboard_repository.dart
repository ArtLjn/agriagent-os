import '../api/api_client.dart';
import '../api/api_models.dart';

class DashboardRepository {
  DashboardRepository(this.client);

  final ApiClient client;

  Future<DailyAdvice> getDailyAdvice({int? cycleId}) async {
    final data = await client.getMap('/dashboard');
    return DailyAdvice.fromDashboard(data);
  }

  Future<DailyAdvice> refreshDailyAdvice({int? cycleId}) async {
    throw const UnsupportedApiException('v2 暂不提供每日 AI 建议刷新接口');
  }

  Future<ApiRecord> createReport(
      {int? cycleId, String reportType = 'weekly'}) async {
    throw const UnsupportedApiException('v2 暂不提供报告生成接口');
  }

  Future<List<ApiRecord>> listAdviceHistory(
      {int? cycleId, int limit = 20}) async {
    throw const UnsupportedApiException('v2 暂不提供建议历史接口');
  }

  Future<List<ApiRecord>> listReportHistory(
      {int? cycleId, int limit = 20}) async {
    throw const UnsupportedApiException('v2 暂不提供报告历史接口');
  }

  Future<PageResult<ApiRecord>> listReports(
      {int page = 1, int size = 10}) async {
    throw const UnsupportedApiException('v2 暂不提供报告列表接口');
  }

  Future<Map<String, dynamic>> getForecast({
    int days = 7,
    String? location,
    double? lat,
    double? lon,
  }) async {
    return client.getMap('/weather', query: {
      'days': days,
      'location': location,
      'lat': lat,
      'lon': lon,
    });
  }

  Future<Map<String, dynamic>> getUnsettledLaborSummary() {
    return client.getMap('/work-orders/labor/unsettled-summary');
  }

  Future<PageResult<ApiRecord>> getWorkOrders(
      {int page = 1, int size = 10}) async {
    final data = await client.getMap('/work-orders', query: {
      'page': page,
      'page_size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<void> loadOverview() async {
    await Future.wait([
      client.get('/dashboard'),
      getForecast(),
      client.get('/work-orders'),
      client.get('/work-orders/labor/unsettled-summary'),
    ]);
  }
}
