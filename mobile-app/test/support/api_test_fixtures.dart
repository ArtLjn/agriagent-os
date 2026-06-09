import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

class RecordingAdapter implements HttpClientAdapter {
  RecordingAdapter(this.responses);

  final Map<String, Object?> responses;
  final List<RecordedRequest> requests = [];

  RecordedRequest find(String method, String path) {
    return requests.singleWhere(
      (request) => request.method == method && request.path == path,
      orElse: () => throw StateError('未找到请求 $method $path'),
    );
  }

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final data = options.data;
    requests.add(
      RecordedRequest(
        method: options.method,
        path: options.path,
        query: Map<String, dynamic>.from(options.queryParameters),
        data: data is Map ? Map<String, dynamic>.from(data) : data,
        headers: Map<String, dynamic>.from(options.headers),
      ),
    );
    final response = responses['${options.method} ${options.path}'] ??
        responses[options.path];
    if (response == null && options.method != 'GET') {
      return ResponseBody.fromString(
        jsonEncode({'message': '未配置测试接口 ${options.method} ${options.path}'}),
        500,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    return ResponseBody.fromString(
      jsonEncode(response ?? {'message': 'ok'}),
      200,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }
}

class StreamingAdapter implements HttpClientAdapter {
  StreamingAdapter([String? body])
      : body = body ??
            [
              'data: {"content":"建议"}\n\n',
              'data: {"content":"傍晚浇水"}\n\n',
              'data: {"skills":["weather"]}\n\n',
              'data: [DONE]\n\n',
            ].join();

  final String body;
  final List<RecordedRequest> requests = [];

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final data = options.data;
    requests.add(
      RecordedRequest(
        method: options.method,
        path: options.path,
        query: Map<String, dynamic>.from(options.queryParameters),
        data: data is Map ? Map<String, dynamic>.from(data) : data,
        headers: Map<String, dynamic>.from(options.headers),
      ),
    );
    return ResponseBody.fromString(
      body,
      200,
      headers: {
        Headers.contentTypeHeader: ['text/event-stream'],
      },
    );
  }
}

class RecordedRequest {
  RecordedRequest({
    required this.method,
    required this.path,
    required this.query,
    required this.data,
    required this.headers,
  });

  final String method;
  final String path;
  final Map<String, dynamic> query;
  final Object? data;
  final Map<String, dynamic> headers;
}

final userResponse = {
  'id': 'u1',
  'phone': '13800138000',
  'nickname': '农友',
  'avatar_url': null,
  'role': 'user',
  'status': 'active',
  'created_at': '2026-06-08T08:00:00',
};

final tokenResponse = {
  'access_token': 'token-1',
  'token_type': 'bearer',
  'user': userResponse,
};

final settingsResponse = {
  'display_name': '农友',
  'default_city': '寿光',
  'default_lat': 36.8,
  'default_lon': 118.7,
};

final versionResponse = {
  'latest_version': '0.1.0',
  'latest_version_code': 4,
  'download_url': 'https://example.test/app.apk',
  'changelog': '更新',
  'force_update': false,
};

final conversationResponse = {
  'id': 1,
  'session_id': 's1',
  'status': 'active',
  'title': '问答',
  'preview': '今天浇水吗',
  'category': '对话',
  'created_at': '2026-06-08T08:00:00',
  'last_active_at': '2026-06-08T08:01:00',
};

final messageResponse = {
  'id': 2,
  'role': 'assistant',
  'content': '建议傍晚浇水',
  'skills': ['weather'],
  'pending_action': null,
  'created_at': '2026-06-08T08:02:00',
};

final dailyAdviceResponse = {
  'cycle_id': 7,
  'preview': '注意控水',
  'items': [
    {'title': '浇水', 'detail': '傍晚少量浇水', 'priority': 1, 'icon': 'water'}
  ],
  'created_at': '2026-06-08T08:00:00',
  'advice': '浇水: 傍晚少量浇水',
};

final reportResponse = {
  'cycle_id': 7,
  'report_type': 'weekly',
  'content': '本周良好',
  'structured_data': null,
  'created_at': '2026-06-08T08:00:00',
};

final adviceHistoryResponse = {
  'id': 1,
  'cycle_id': 7,
  'record_type': 'daily',
  'content': '注意控水',
  'created_at': '2026-06-08T08:00:00',
};

final reportHistoryResponse = {
  'id': 1,
  'cycle_id': 7,
  'report_type': 'weekly',
  'content': '本周良好',
  'structured_data': null,
  'created_at': '2026-06-08T08:00:00',
};

final paginatedReportsResponse = {
  'items': [reportHistoryResponse],
  'total': 1
};

final costRecordResponse = {
  'id': 1,
  'cycle_id': 7,
  'record_type': 'cost',
  'category': '肥料',
  'amount': '200',
  'settled_amount': '0',
  'settlement_status': 'unsettled',
  'unsettled_amount': '200',
  'record_date': '2026-06-08',
  'note': null,
  'record_subtype': null,
  'counterparty': '老王',
  'due_date': null,
  'settled_at': null,
  'parent_record_id': null,
  'source_type': null,
  'source_id': null,
  'source_active_key': null,
  'source_label': null,
  'created_at': '2026-06-08T08:00:00',
};

final paginatedCostsResponse = {
  'items': [costRecordResponse],
  'total': 1
};

final yearlySummaryResponse = {
  'year': 2026,
  'total_cost': '200',
  'total_income': '0',
  'net_profit': '-200',
  'settled_cost': '0',
  'settled_income': '0',
  'unsettled_cost': '200',
  'unsettled_income': '0',
  'by_category': {'肥料': '200'},
};

final cycleProfitResponse = {
  'cycle_id': 7,
  'total_cost': '200',
  'total_income': '0',
  'net_profit': '-200',
  'settled_cost': '0',
  'settled_income': '0',
  'unsettled_cost': '200',
  'unsettled_income': '0',
  'labor_cost': '0',
  'labor_entry_cost': '0',
  'operation_labor_cost': '0',
};

final costParseResponse = {
  'record_type': 'cost',
  'category': '肥料',
  'amount': '200',
  'record_date': '2026-06-08',
  'note': null,
};

final categoryResponse = {
  'id': 1,
  'farm_id': 1,
  'name': '肥料',
  'type': 'cost',
  'icon': 'leaf',
  'sort_order': 1,
  'is_default': true,
};

final debtsResponse = {
  'items': [costRecordResponse],
  'total': 1,
  'summary': [
    {
      'counterparty': '老王',
      'total_debt': '200',
      'total_settled': '0',
      'remaining': '200',
      'record_count': 1,
    }
  ],
};

final weatherResponse = {
  'location': '寿光',
  'forecast': [
    {'date': '2026-06-08', 'weather': '晴'}
  ],
  'warnings': [],
};

final cycleResponse = {
  'id': 7,
  'name': '春茬',
  'crop_template_id': 1,
  'start_date': '2026-03-01',
  'field_name': '一号棚',
  'total_area_mu': '3.5',
  'season': '春季',
  'batch_note': null,
  'status': 'active',
  'stages': [],
  'unit_count': 1,
  'unit_area_mu': '3.5',
  'current_stage_name': '生长期',
};

final paginatedCyclesResponse = {
  'items': [cycleResponse],
  'total': 1
};

final cycleParseResponse = {
  'name': '春茬番茄',
  'crop_template_id': 1,
  'start_date': '2026-03-01',
  'field_name': '一号棚',
};

final plantingUnitResponse = {
  'id': 3,
  'farm_id': 1,
  'cycle_id': 7,
  'name': 'A棚',
  'area_mu': '3.5',
  'planted_date': '2026-03-01',
  'status': 'active',
  'note': null,
  'created_at': '2026-06-08T08:00:00',
};

final workerResponse = {
  'id': 4,
  'farm_id': 1,
  'name': '张三',
  'phone': null,
  'default_pay_type': 'daily',
  'default_unit_price': '200',
  'note': null,
  'status': 'active',
  'created_at': '2026-06-08T08:00:00',
};

final paginatedWorkersResponse = {
  'items': [workerResponse],
  'total': 1
};

final operationTypeResponse = {
  'name': '浇水',
  'crop': null,
  'is_builtin': true,
  'sort_order': 1,
};

final wageResponse = {
  'id': 5,
  'farm_id': 1,
  'work_order_id': 9,
  'worker_id': 4,
  'worker_name': '张三',
  'pay_type': 'daily',
  'quantity': '1',
  'unit_price': '200',
  'payable_amount': '200',
  'paid_amount': '0',
  'unpaid_amount': '200',
  'settlement_status': 'unsettled',
  'note': null,
  'cycle_id': 7,
  'operation_type': '浇水',
  'cost_record_id': 1,
};

final workOrderResponse = {
  'id': 9,
  'farm_id': 1,
  'cycle_id': 7,
  'cycle_name': '春茬',
  'operation_type': '浇水',
  'operation_date': '2026-06-08',
  'scope_type': 'cycle',
  'unit_ids': [3],
  'unit_names': ['A棚'],
  'note': null,
  'photo_urls': null,
  'labor_entries': [],
  'labor_cost_record_id': null,
  'total_payable_amount': '0',
  'total_paid_amount': '0',
  'total_unpaid_amount': '0',
  'created_at': '2026-06-08T08:00:00',
};

final paginatedWorkOrdersResponse = {
  'items': [workOrderResponse],
  'total': 1
};

final recentOperationResponse = {
  'source_type': 'work_order',
  'source_id': 9,
  'cycle_id': 7,
  'cycle_name': '春茬',
  'operation_type': '浇水',
  'operation_date': '2026-06-08',
  'scope_text': '全部',
  'note': null,
};

final unsettledLaborSummaryResponse = {
  'total_payable': '200',
  'total_paid': '0',
  'total_unpaid': '200',
  'entry_count': 1,
};

final logResponse = {
  'id': 11,
  'cycle_id': 7,
  'operation_type': '浇水',
  'operation_date': '2026-06-08',
  'operation_time': null,
  'note': '已处理',
  'photo_urls': null,
  'created_at': '2026-06-08T08:00:00',
};

final paginatedLogsResponse = {
  'items': [logResponse],
  'total': 1
};

final smartFillScenariosResponse = {
  'items': [
    {
      'key': 'ledger.record',
      'title': '记账',
      'description': '解析收支',
      'legacy_endpoint': '/costs/parse',
      'enabled': true,
      'request_example': '买肥料 200',
    }
  ],
};

final smartFillParseResponse = {
  'scene': 'ledger.record',
  'draft': {'amount': '200'},
  'missing_fields': [],
  'warnings': [],
  'trace_id': 'trace-1',
};
