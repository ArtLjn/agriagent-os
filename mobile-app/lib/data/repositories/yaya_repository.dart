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
    await for (final data in _eventData(response.data)) {
      final trimmed = data.trim();
      if (trimmed.isEmpty) continue;
      if (trimmed == '[DONE]') {
        yield const YayaStreamEvent(done: true);
      } else {
        yield _parseEvent(trimmed);
      }
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

  Stream<String> _eventData(Object? data) async* {
    final dataLines = <String>[];
    await for (final line in _eventLines(data)) {
      if (line.isEmpty) {
        if (dataLines.isNotEmpty) {
          yield dataLines.join('\n');
          dataLines.clear();
        }
        continue;
      }
      if (line.startsWith('data:')) {
        dataLines.add(line.substring(5).trimLeft());
      }
    }
    if (dataLines.isNotEmpty) {
      yield dataLines.join('\n');
    }
  }

  YayaStreamEvent _parseEvent(String data) {
    try {
      return YayaStreamEvent.fromJson(jsonDecode(data) as Map<String, dynamic>);
    } on FormatException {
      return const YayaStreamEvent(error: '芽芽回复解析失败，请稍后重试');
    }
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
    final eventType = json['type'] as String?;
    final data = json['data'];
    final pendingAction = eventType == 'pending_action' && data is Map
        ? Map<String, dynamic>.from(data)
        : json['pending_action'] as Map<String, dynamic>?;
    return YayaStreamEvent(
      content:
          eventType == 'content' ? data as String? : json['content'] as String?,
      skills:
          (json['skills'] as List<dynamic>? ?? []).map((v) => '$v').toList(),
      pendingAction: pendingAction,
      error: json['error'] as String?,
    );
  }

  final String? content;
  final List<String> skills;
  final Map<String, dynamic>? pendingAction;
  final String? error;
  final bool done;
}
