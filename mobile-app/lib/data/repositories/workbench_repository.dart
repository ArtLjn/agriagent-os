import '../api/api_client.dart';

class WorkbenchRepository {
  WorkbenchRepository(this.client);

  final ApiClient client;

  Future<void> warmUp() async {
    await Future.wait([
      client.get('/cycles'),
      client.get('/planting/units'),
      client.get('/planting/workers'),
      client.get('/planting/operation-types'),
      client.get('/logs'),
    ]);
  }
}
