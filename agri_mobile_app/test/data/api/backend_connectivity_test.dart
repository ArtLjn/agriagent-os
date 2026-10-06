import 'package:dio/dio.dart';
import 'dart:collection';
import 'package:farm_manager_app/data/api/api_client.dart';
import 'package:farm_manager_app/app/app_dependencies.dart';
import 'package:farm_manager_app/data/repositories/dashboard_repository.dart';
import 'package:farm_manager_app/features/home/home_controller.dart';
import 'package:farm_manager_app/data/repositories/yaya_repository.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/api_test_fixtures.dart';

void main() {
  test('分页读取账单并向下一页传递正确参数', () async {
    final adapter = RecordingAdapter({
      '/cost-records': ListQueue<Object?>.from([
        {
          'items': [
            {'id': 1}
          ],
          'total': 2
        },
        {
          'items': [
            {'id': 2}
          ],
          'total': 2
        },
      ]),
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://backend.test/api/v2'))
      ..httpClientAdapter = adapter;
    final data = await ApiClient(dio: dio).getAllPages('/cost-records');
    expect(data['items'], [
      {'id': 1},
      {'id': 2}
    ]);
    expect(adapter.requests.map((request) => request.query['page']), [1, 2]);
    expect(
        adapter.requests.every((request) => request.query['page_size'] == 100),
        isTrue);
  });

  test('历史消息先取最新页，再把旧页插到前面', () async {
    final adapter = RecordingAdapter({
      '/conversations/s1/messages': ListQueue<Object?>.from([
        {
          'items': [
            {'role': 'assistant', 'content': '新回复'}
          ],
          'has_more': true,
          'next_cursor': 'older'
        },
        {
          'items': [
            {'role': 'user', 'content': '旧问题'}
          ],
          'has_more': false
        },
      ]),
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://backend.test/api/v2'))
      ..httpClientAdapter = adapter;
    final messages =
        await YayaRepository(ApiClient(dio: dio)).loadMessages('s1');
    expect(messages.map((message) => message.content), ['旧问题', '新回复']);
    expect(adapter.requests.last.query['cursor'], 'older');
  });

  test('422 错误展示中文字段提示，登录过期单独提示', () {
    final options = RequestOptions(path: '/farm-logs');
    final validation = DioException(
        requestOptions: options,
        response: Response(
          requestOptions: options,
          statusCode: 422,
          data: {
            'detail': {
              'code': 'validation_error',
              'meta': {
                'errors': [
                  {
                    'loc': ['body', 'cycle_id'],
                    'type': 'missing'
                  },
                ]
              },
            }
          },
        ));
    expect(ApiClient.userMessageFor(validation), '请填写关联茬口');
    expect(
        ApiClient.userMessageFor(DioException(
            requestOptions: options,
            response: Response(requestOptions: options, statusCode: 401))),
        '登录已过期，请重新登录');
  });
  tearDown(() => debugDefaultTargetPlatformOverride = null);

  test('Android 默认通过模拟器宿主机别名连接两个本机服务', () {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    final dependencies = BackendAppDependencies();

    expect(ApiClient().baseUrl, 'http://10.0.2.2:9876/api/v2');
    expect(dependencies.client.baseUrl, 'http://10.0.2.2:9876/api/v2');
    expect(dependencies.agentClient.baseUrl, 'http://10.0.2.2:8000/api/v2');
  });

  test('其他平台默认直接连接本机回环地址', () {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    final dependencies = BackendAppDependencies();

    expect(dependencies.client.baseUrl, 'http://127.0.0.1:9876/api/v2');
    expect(dependencies.agentClient.baseUrl, 'http://127.0.0.1:8000/api/v2');
  });

  test('显式服务器配置和注入客户端保持优先', () {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    final business = ApiClient(baseUrl: 'https://business.example.com/api/v2');
    final agent = ApiClient(baseUrl: 'https://agent.example.com/api/v2');
    final dependencies =
        BackendAppDependencies(client: business, agentClient: agent);

    expect(dependencies.client, same(business));
    expect(dependencies.agentClient, same(agent));
    expect(dependencies.client.baseUrl, 'https://business.example.com/api/v2');
    expect(
        dependencies.agentClient.baseUrl, 'https://agent.example.com/api/v2');
  });

  test('首页按 v2 合同加载概览和未结工资，避开不存在的作业单子路由', () async {
    final adapter = RecordingAdapter({
      '/dashboard': {'location': '苏州', 'active_cycles': []},
      '/weather': backendWeatherResponse,
      '/work-orders': paginatedWorkOrdersResponse,
      '/labor/unsettled-summary': unsettledLaborSummaryResponse,
    }, statusCodes: {
      '/work-orders/labor/unsettled-summary': 401,
    });
    final dio = Dio(BaseOptions(baseUrl: 'http://10.0.2.2:9876/api/v2'))
      ..httpClientAdapter = adapter;
    final client = ApiClient(dio: dio)..setAccessToken('test-token');
    final repository = DashboardRepository(client);

    await repository.loadOverview();
    final model = await HomeController(repository: repository).load();

    expect(model.headline, '苏州暂无每日 AI 建议');
    expect(model.unsettledLaborText, '¥200');
    expect(model.workOrderCountText, '1项');
    expect(model.weatherText, '20℃');
    expect(adapter.requests.map((request) => request.path).toSet(), {
      '/dashboard',
      '/weather',
      '/work-orders',
      '/labor/unsettled-summary',
    });
    expect(
        adapter.requests.every((request) =>
            request.headers['Authorization'] == 'Bearer test-token'),
        isTrue);
  });
}
