import 'package:dio/dio.dart';
import 'package:farm_manager_app/app/app_dependencies.dart';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/data/repositories/yaya_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  test('应用依赖将 Business 与 Agent 分为两个客户端', () {
    final business = ApiClient(
      baseUrl: 'http://192.168.1.13:9876/api/v2',
    );
    final agent = ApiClient(
      baseUrl: 'http://192.168.1.13:8000/api/v2',
    );
    final dependencies = BackendAppDependencies(
      client: business,
      agentClient: agent,
    );

    expect(dependencies.profile.client, same(business));
    expect(dependencies.yaya.client, same(agent));
  });

  test('v2 SSE 使用 conversation_id 并解析事件名与最终答复', () async {
    final adapter = StreamingAdapter([
      'event: meta\n',
      'data: {"turn_id":"t1","conversation_id":"c1"}\n\n',
      'event: final_answer_delta\n',
      'data: {"delta":"建议"}\n\n',
      'event: final_answer\n',
      'data: {"text":"建议傍晚浇水"}\n\n',
      'event: done\n',
      'data: {"status":"completed","turn_id":"t1"}\n\n',
    ].join());
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:8000/api/v2'))
      ..httpClientAdapter = adapter;
    final repository = YayaRepository(ApiClient(dio: dio));

    final events =
        await repository.streamMessage('今天浇水吗', sessionId: 'c1').toList();

    expect(adapter.requests.single.path, '/chat');
    final requestData =
        Map<String, dynamic>.from(adapter.requests.single.data as Map);
    expect(requestData['message'], '今天浇水吗');
    expect(requestData['conversation_id'], 'c1');
    expect(requestData['client_request_id'], isA<String>());
    expect(events.map((event) => event.eventType), [
      'meta',
      'final_answer_delta',
      'final_answer',
      'done',
    ]);
    expect(events[1].content, '建议');
    expect(events[2].content, '建议傍晚浇水');
    expect(events.last.done, isTrue);
  });

  test('v2 审批使用 approve 接口而不是发送确认文本', () async {
    final adapter = RecordingAdapter({
      'POST /approve': {'ok': true}
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://192.168.1.13:8000/api/v2'))
      ..httpClientAdapter = adapter;
    final repository = YayaRepository(ApiClient(dio: dio));

    await repository.approve(turnId: 't1', decision: true);

    final request = adapter.find('POST', '/approve');
    expect(request.data, {
      'turn_id': 't1',
      'decision': true,
      'reason': '',
    });
  });

  test('审批事件保留 turn_id 供控制器提交 HITL 决议', () {
    final event = YayaStreamEvent.fromJson(
      {
        'data': {
          'turn_id': 't1',
          'tool_name': 'create_cost_record',
          'arguments': {'amount': 200},
        },
      },
      eventType: 'approval_required',
    );

    expect(event.turnId, 't1');
    expect(event.pendingAction?['tool_name'], 'create_cost_record');
  });
}
