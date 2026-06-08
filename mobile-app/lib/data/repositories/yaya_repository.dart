import '../api/api_client.dart';
import '../api/api_models.dart';

class YayaRepository {
  YayaRepository(this.client);

  final ApiClient client;

  Future<ChatReply> sendMessage(
    String message, {
    int? cycleId,
    String? sessionId,
  }) async {
    final data = await client.postMap('/agent/chat', data: {
      'cycle_id': cycleId,
      'message': message,
      'session_id': sessionId,
    }..removeWhere((_, value) => value == null));
    return ChatReply.fromJson(data);
  }

  Future<List<ConversationSummary>> loadConversations({int limit = 20}) async {
    final data = await client.getList('/agent/conversations', query: {
      'limit': limit,
    });
    return data
        .map((item) => ConversationSummary.fromJson(
              Map<String, dynamic>.from(item as Map),
            ))
        .toList();
  }

  Future<List<ConversationMessage>> loadMessages(String sessionId) async {
    final data = await client.getList('/agent/conversations/$sessionId/messages');
    return data
        .map((item) => ConversationMessage.fromJson(
              Map<String, dynamic>.from(item as Map),
            ))
        .toList();
  }
}
