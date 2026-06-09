import '../api/api_client.dart';
import '../api/api_models.dart';

class DashboardRepository {
  DashboardRepository(this.client);

  final ApiClient client;

  Future<DailyAdvice> getDailyAdvice({int? cycleId}) async {
    final data =
        await client.getMap('/agent/daily', query: {'cycle_id': cycleId});
    return DailyAdvice.fromJson(data);
  }

  Future<DailyAdvice> refreshDailyAdvice({int? cycleId}) async {
    final data = await client.postMap(
      '/agent/daily/refresh',
      query: {'cycle_id': cycleId},
    );
    return DailyAdvice.fromJson(data);
  }

  Future<ApiRecord> createReport(
      {int? cycleId, String reportType = 'weekly'}) async {
    final data = await client.postMap('/agent/report',
        data: {
          'cycle_id': cycleId,
          'report_type': reportType,
        }..removeWhere((_, value) => value == null));
    return ApiRecord.fromJson(data);
  }

  Future<List<ApiRecord>> listAdviceHistory(
      {int? cycleId, int limit = 20}) async {
    final data = await client.getList('/agent/advice-history', query: {
      'cycle_id': cycleId,
      'limit': limit,
    });
    return _records(data);
  }

  Future<List<ApiRecord>> listReportHistory(
      {int? cycleId, int limit = 20}) async {
    final data = await client.getList('/agent/report-history', query: {
      'cycle_id': cycleId,
      'limit': limit,
    });
    return _records(data);
  }

  Future<PageResult<ApiRecord>> listReports(
      {int page = 1, int size = 10}) async {
    final data = await client.getMap('/agent/reports', query: {
      'page': page,
      'size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<Map<String, dynamic>> getForecast({
    int days = 7,
    String? location,
    double? lat,
    double? lon,
  }) async {
    var forecastLocation = location;
    var forecastLat = lat;
    var forecastLon = lon;
    if ((forecastLocation == null || forecastLocation.trim().isEmpty) &&
        (forecastLat == null || forecastLon == null)) {
      final settings = await client.getMap('/settings');
      forecastLocation = settings['default_city'] as String?;
      forecastLat = (settings['default_lat'] as num?)?.toDouble();
      forecastLon = (settings['default_lon'] as num?)?.toDouble();
    }
    return client.getMap('/weather/forecast', query: {
      'days': days,
      'location': forecastLocation,
      'lat': forecastLat,
      'lon': forecastLon,
    });
  }

  Future<Map<String, dynamic>> getUnsettledLaborSummary() {
    return client.getMap('/planting/labor/unsettled-summary');
  }

  Future<PageResult<ApiRecord>> getWorkOrders(
      {int page = 1, int size = 10}) async {
    final data = await client.getMap('/planting/work-orders', query: {
      'page': page,
      'size': size,
    });
    return PageResult.fromJson(data, ApiRecord.fromJson);
  }

  Future<void> loadOverview() async {
    await Future.wait([
      client.get('/agent/daily'),
      getForecast(),
      client.get('/planting/work-orders'),
      client.get('/planting/labor/unsettled-summary'),
    ]);
  }

  List<ApiRecord> _records(List<dynamic> data) {
    return data
        .map((item) =>
            ApiRecord.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
  }
}
