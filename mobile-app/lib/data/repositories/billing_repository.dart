import '../api/api_client.dart';

class BillingRepository {
  BillingRepository(this.client);

  final ApiClient client;

  Future<void> loadBillingSummary() async {
    await Future.wait([
      client.get('/costs'),
      client.get('/costs/summary/2026'),
      client.get('/debts'),
    ]);
  }
}
