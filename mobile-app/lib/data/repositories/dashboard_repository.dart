import '../api/api_client.dart';

class DashboardRepository {
  DashboardRepository(this.client);

  final ApiClient client;

  Future<void> loadOverview() async {
    await Future.wait([
      client.get('/agent/daily'),
      client.get('/weather/forecast'),
      client.get('/planting/work-orders'),
      client.get('/planting/labor/unsettled-summary'),
    ]);
  }
}
