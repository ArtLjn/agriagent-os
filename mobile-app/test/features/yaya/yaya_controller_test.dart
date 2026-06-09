import 'dart:async';

import 'package:dio/dio.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/api/api_models.dart';
import 'package:farm_manager_app/data/repositories/yaya_repository.dart';
import 'package:farm_manager_app/features/yaya/yaya_controller.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  test('流式发送会追加用户消息并增量拼接芽芽回复', () async {
    final repository = FakeStreamingYayaRepository([
      const YayaStreamEvent(content: '建议'),
      const YayaStreamEvent(content: '傍晚浇水'),
      const YayaStreamEvent(skills: ['weather']),
      const YayaStreamEvent(
        pendingAction: {'type': 'confirm'},
      ),
      const YayaStreamEvent(done: true),
    ]);
    final controller = YayaController(repository: repository);

    await controller.send('今天浇水吗');

    expect(controller.messages.map((item) => item.content), [
      '今天浇水吗',
      '建议傍晚浇水',
    ]);
    expect(controller.lastSkills, ['weather']);
    expect(controller.pendingAction, {'type': 'confirm'});
    expect(controller.sending, false);
  });

  test('流式错误会保留用户消息并展示错误', () async {
    final repository = FakeStreamingYayaRepository([
      const YayaStreamEvent(error: '模型未配置'),
    ]);
    final controller = YayaController(repository: repository);

    await controller.send('今天浇水吗');

    expect(controller.messages.single.content, '今天浇水吗');
    expect(controller.errorMessage, '模型未配置');
    expect(controller.sending, false);
  });

  test('加载历史会话和消息', () async {
    final adapter = RecordingAdapter({
      '/agent/conversations': [conversationResponse],
      '/agent/conversations/s1/messages': [messageResponse],
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://localhost:8099'));
    dio.httpClientAdapter = adapter;
    final controller = YayaController(
      repository: YayaRepository(ApiClient(dio: dio)),
    );

    await controller.loadConversations();
    await controller.openConversation('s1');

    expect(controller.conversations.single.title, '问答');
    expect(controller.activeSessionId, 's1');
    expect(controller.messages.single.content, '建议傍晚浇水');
  });

  test('dispose 后延迟流完成不会抛 disposed notifier 异常', () async {
    final repository = DelayedStreamingYayaRepository();
    final controller = YayaController(repository: repository);

    final sendFuture = controller.send('今天浇水吗');
    await Future<void>.delayed(Duration.zero);
    controller.dispose();
    repository.complete([
      const YayaStreamEvent(content: '建议'),
      const YayaStreamEvent(done: true),
    ]);

    await sendFuture;
  });

  test('发送中切换历史会话不清空当前消息并提示等待', () async {
    final repository = DelayedStreamingYayaRepository();
    final controller = YayaController(repository: repository);

    final sendFuture = controller.send('今天浇水吗');
    await Future<void>.delayed(Duration.zero);
    await controller.openConversation('s1');

    expect(controller.messages.map((item) => item.content), [
      '今天浇水吗',
      '',
    ]);
    expect(controller.errorMessage, '请等待芽芽回复完成后再切换会话');

    repository.complete([
      const YayaStreamEvent(content: '建议'),
      const YayaStreamEvent(done: true),
    ]);
    await sendFuture;

    expect(controller.messages.map((item) => item.content), [
      '今天浇水吗',
      '建议',
    ]);
  });
}

class FakeStreamingYayaRepository extends YayaRepository {
  FakeStreamingYayaRepository(this.events) : super(ApiClient());

  final List<YayaStreamEvent> events;

  @override
  Stream<YayaStreamEvent> streamMessage(
    String message, {
    int? cycleId,
    String? sessionId,
  }) async* {
    for (final event in events) {
      yield event;
    }
  }
}

class DelayedStreamingYayaRepository extends YayaRepository {
  DelayedStreamingYayaRepository() : super(ApiClient());

  final _controller = StreamController<YayaStreamEvent>();

  void complete(List<YayaStreamEvent> events) {
    for (final event in events) {
      _controller.add(event);
    }
    _controller.close();
  }

  @override
  Stream<YayaStreamEvent> streamMessage(
    String message, {
    int? cycleId,
    String? sessionId,
  }) {
    return _controller.stream;
  }

  @override
  Future<List<ConversationMessage>> loadMessages(String sessionId) async {
    return const [
      ConversationMessage(
        id: 1,
        role: 'assistant',
        content: '历史消息',
      ),
    ];
  }
}
