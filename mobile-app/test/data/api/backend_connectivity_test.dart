import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('默认后端地址指向 localhost:8099', () {
    final client = ApiClient();
    expect(client.baseUrl, 'http://localhost:8099');
  });
}
