import '../api/api_client.dart';

class YayaRepository {
  YayaRepository(this.client);

  final ApiClient client;

  Future<void> sendMessage(String message) async {
    await client.post('/agent/chat', data: {'message': message});
  }

  Future<void> loadConversations() async {
    await client.get('/agent/conversations');
  }
}
