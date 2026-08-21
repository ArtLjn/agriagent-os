import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('默认后端地址指向局域网 Business 服务', () {
    final client = ApiClient();
    expect(client.baseUrl, 'http://192.168.1.13:9876/api/v2');
  });
}
