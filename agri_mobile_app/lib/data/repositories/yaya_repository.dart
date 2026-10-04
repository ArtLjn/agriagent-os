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
    final conversationId =
        sessionId ?? 'app-${DateTime.now().microsecondsSinceEpoch}';
    final response = await client.post(
      '/chat',
      data: {
        'message': message,
        'conversation_id': conversationId,
        'client_request_id': 'mobile-${DateTime.now().microsecondsSinceEpoch}',
      },
      headers: {'Accept': 'text/event-stream'},
      responseType: ResponseType.stream,
    );
    await for (final frame in _eventFrames(response.data)) {
      final trimmed = frame.data.trim();
      if (trimmed.isEmpty) continue;
      if (trimmed == '[DONE]') {
        yield const YayaStreamEvent(done: true);
      } else {
        yield _parseEvent(frame);
      }
    }
  }

  Future<ChatReply> sendMessage(
    String message, {
    int? cycleId,
    String? sessionId,
  }) async {
    throw const UnsupportedApiException('v2 芽芽对话仅提供 SSE 接口');
  }

  Future<void> approve({
    required String turnId,
    required bool decision,
    String reason = '',
  }) async {
    await client.postMap(
      '/approve',
      data: {
        'turn_id': turnId,
        'decision': decision,
        'reason': reason,
      },
    );
  }

  Future<List<ConversationSummary>> loadConversations({int limit = 20}) async {
    final conversations = <ConversationSummary>[];
    String? cursor;
    final cursors = <String>{};
    do {
      final raw = (await client.get('/conversations', query: {
        'limit': limit,
        if (cursor != null) 'cursor': cursor,
      }))
          .data;
      final items =
          raw is Map ? ApiClient.asList(raw['items']) : ApiClient.asList(raw);
      conversations.addAll(items.map((item) => ConversationSummary.fromJson(
          Map<String, dynamic>.from(item as Map))));
      cursor = raw is Map && raw['has_more'] == true
          ? raw['next_cursor']?.toString()
          : null;
      if (cursor != null && !cursors.add(cursor)) {
        throw StateError('会话分页游标重复');
      }
    } while (cursor != null);
    return conversations;
  }

  Future<List<ConversationMessage>> loadMessages(String conversationId) async {
    final messages = <ConversationMessage>[];
    String? cursor;
    final cursors = <String>{};
    do {
      final raw = await client
          .getMap('/conversations/$conversationId/messages', query: {
        'limit': 100,
        if (cursor != null) 'cursor': cursor,
      });
      final items = ApiClient.asList(raw['items']);
      final page = items
          .map((item) => ConversationMessage.fromJson(
              Map<String, dynamic>.from(item as Map)))
          .toList();
      // 后端先返回最新页，每个页面内部按时间正序，旧页应插在已有消息之前。
      messages.insertAll(0, page);
      cursor = raw['has_more'] == true ? raw['next_cursor']?.toString() : null;
      if (cursor != null && !cursors.add(cursor)) {
        throw StateError('消息分页游标重复');
      }
    } while (cursor != null);
    return messages;
  }

  Future<List<YayaSkill>> loadSkills() async {
    throw const UnsupportedApiException('v2 暂不提供技能列表接口');
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

  Stream<_SseFrame> _eventFrames(Object? data) async* {
    var eventType = '';
    final dataLines = <String>[];
    await for (final line in _eventLines(data)) {
      if (line.isEmpty) {
        if (dataLines.isNotEmpty) {
          yield _SseFrame(eventType: eventType, data: dataLines.join('\n'));
          eventType = '';
          dataLines.clear();
        }
        continue;
      }
      if (line.startsWith('event:')) {
        eventType = line.substring(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.add(line.substring(5).trimLeft());
      }
    }
    if (dataLines.isNotEmpty) {
      yield _SseFrame(eventType: eventType, data: dataLines.join('\n'));
    }
  }

  YayaStreamEvent _parseEvent(_SseFrame frame) {
    try {
      final json = jsonDecode(frame.data);
      if (json is! Map) return const YayaStreamEvent(error: '芽芽回复格式无效');
      return YayaStreamEvent.fromJson(
        Map<String, dynamic>.from(json),
        eventType: frame.eventType,
      );
    } on FormatException {
      return const YayaStreamEvent(error: '芽芽回复解析失败，请稍后重试');
    }
  }
}

class _SseFrame {
  const _SseFrame({required this.eventType, required this.data});

  final String eventType;
  final String data;
}

class YayaStreamEvent {
  const YayaStreamEvent({
    this.content,
    this.skills = const [],
    this.pendingAction,
    this.error,
    this.done = false,
    this.eventType,
    this.turnId,
    this.conversationId,
    this.status,
  });

  factory YayaStreamEvent.fromJson(
    Map<String, dynamic> json, {
    String? eventType,
  }) {
    final type = eventType?.trim().isNotEmpty == true
        ? eventType!
        : (json['type'] as String? ?? '');
    final rawData = json['data'];
    final data = rawData is Map
        ? Map<String, dynamic>.from(rawData)
        : <String, dynamic>{};
    final merged = <String, dynamic>{...json, ...data};
    final pending = type == 'approval_required' || type == 'pending_action'
        ? <String, dynamic>{...merged, 'type': type}
        : json['pending_action'] is Map
            ? Map<String, dynamic>.from(json['pending_action'] as Map)
            : null;
    final content = switch (type) {
      'final_answer_delta' => '${merged['delta'] ?? ''}',
      'final_answer' => '${merged['text'] ?? ''}',
      'content' => rawData is String ? rawData : '${merged['content'] ?? ''}',
      _ => json['content'] as String?,
    };
    final error = {
      'error',
      'turn.failed',
      'turn.terminated',
      'timeout',
      'cancelled'
    }.contains(type)
        ? '${merged['message'] ?? merged['error'] ?? '芽芽处理失败'}'
        : json['error'] as String?;
    return YayaStreamEvent(
      content: content?.isEmpty == true ? null : content,
      skills: (json['skills'] as List<dynamic>? ?? [])
          .map((value) => '$value')
          .toList(),
      pendingAction: pending,
      error: error,
      done: type == 'done',
      eventType: type,
      turnId: '${merged['turn_id'] ?? ''}'.trim().isEmpty
          ? null
          : '${merged['turn_id']}',
      conversationId: '${merged['conversation_id'] ?? ''}'.trim().isEmpty
          ? null
          : '${merged['conversation_id']}',
      status: merged['status'] as String?,
    );
  }

  final String? content;
  final List<String> skills;
  final Map<String, dynamic>? pendingAction;
  final String? error;
  final bool done;
  final String? eventType;
  final String? turnId;
  final String? conversationId;
  final String? status;
}
