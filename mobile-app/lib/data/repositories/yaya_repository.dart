import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../api/api_client.dart';
import '../api/api_models.dart';

class YayaRepository {
  YayaRepository(this.client);

  final ApiClient client;

  Stream<YayaStreamEvent> streamMessage(
    String message, {
    int? cycleId,
    String? sessionId,
  }) async* {
    final response = await client.post(
      '/agent/chat/stream',
      data: {
        'cycle_id': cycleId,
        'message': message,
        'session_id': sessionId,
      }..removeWhere((_, value) => value == null),
      headers: {'Accept': 'text/event-stream'},
      responseType: ResponseType.stream,
    );
    final lines = _eventLines(response.data);
    await for (final line in lines) {
      if (!line.startsWith('data:')) continue;
      final data = line.substring(5).trim();
      if (data.isEmpty) continue;
      if (data == '[DONE]') {
        yield const YayaStreamEvent(done: true);
        continue;
      }
      yield YayaStreamEvent.fromJson(jsonDecode(data) as Map<String, dynamic>);
    }
  }

  Future<ChatReply> sendMessage(
    String message, {
    int? cycleId,
    String? sessionId,
  }) async {
    final data = await client.postMap('/agent/chat',
        data: {
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
    final data =
        await client.getList('/agent/conversations/$sessionId/messages');
    return data
        .map((item) => ConversationMessage.fromJson(
              Map<String, dynamic>.from(item as Map),
            ))
        .toList();
  }

  Stream<String> _eventLines(Object? data) {
    if (data is ResponseBody) {
      return data.stream
          .map<List<int>>((chunk) => chunk)
          .transform(utf8.decoder)
          .transform(const LineSplitter());
    }
    if (data is Stream<List<int>>) {
      return data.transform(utf8.decoder).transform(const LineSplitter());
    }
    if (data is String) {
      return Stream<String>.fromIterable(const LineSplitter().convert(data));
    }
    return Stream<String>.fromIterable(
      const LineSplitter().convert(data?.toString() ?? ''),
    );
  }
}

class YayaStreamEvent {
  const YayaStreamEvent({
    this.content,
    this.skills = const [],
    this.pendingAction,
    this.error,
    this.done = false,
  });

  factory YayaStreamEvent.fromJson(Map<String, dynamic> json) {
    return YayaStreamEvent(
      content: json['content'] as String?,
      skills:
          (json['skills'] as List<dynamic>? ?? []).map((v) => '$v').toList(),
      pendingAction: json['pending_action'] as Map<String, dynamic>?,
      error: json['error'] as String?,
    );
  }

  final String? content;
  final List<String> skills;
  final Map<String, dynamic>? pendingAction;
  final String? error;
  final bool done;
}
