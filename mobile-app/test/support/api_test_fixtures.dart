import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

part 'api_daily_advice_fixture.dart';
part 'api_agent_fixture.dart';

class RecordingAdapter implements HttpClientAdapter {
  RecordingAdapter(this.responses, {this.statusCodes = const {}});

  final Map<String, Object?> responses;
  final Map<String, int> statusCodes;
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
    final key = '${options.method} ${options.path}';
    final response = responses[key] ?? responses[options.path];
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
      statusCodes[key] ?? statusCodes[options.path] ?? 200,
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
  'farm': {
    'id': 1,
    'name': '农友的农场',
    'location': '睢宁县',
  },
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
  'assistant_role': 'warm',
};

final versionResponse = {
  'latest_version': '0.1.0',
  'latest_version_code': 4,
  'download_url': 'https://example.test/app.apk',
  'changelog': '更新',
  'force_update': false,
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

final cropTemplateResponse = {
  'id': 3,
  'name': '番茄',
  'variety': '粉果 306',
  'usage_count': 4,
  'total_cycle_days': 110,
  'stages': [
    {
      'name': '育苗期',
      'duration_days': 18,
      'order_index': 1,
      'key_tasks': '控温、补光',
    },
    {
      'name': '结果期',
      'duration_days': 45,
      'order_index': 2,
      'key_tasks': '疏花、追肥',
    },
  ],
};

final paginatedCropTemplatesResponse = {
  'items': [cropTemplateResponse],
  'total': 1,
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

final backendWeatherResponse = {
  'location': '睢宁县',
  'provider': 'open-meteo',
  'daily': {
    'time': ['2026-06-09'],
    'temperature_2m_max': [32.1],
    'temperature_2m_min': [17.2],
    'precipitation_sum': [0.0],
    'windspeed_10m_max': [11.2],
  },
  'current_weather': {'temperature': 19.8},
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

final paginatedWorkerSummariesResponse = {
  'items': [workerResponse],
  'total': 1
};

final workerSummaryFilterResponse = {
  'items': [
    {
      ...workerResponse,
      'id': 4,
      'name': '张三',
      'status': 'active',
      'unpaid_amount': 0,
      'monthly_work_count': 6,
    },
    {
      ...workerResponse,
      'id': 5,
      'name': '李四',
      'status': 'active',
      'unpaid_amount': 120,
      'monthly_work_count': 4,
    },
    {
      ...workerResponse,
      'id': 6,
      'name': '老王',
      'status': 'inactive',
      'unpaid_amount': 80,
      'monthly_work_count': 3,
    },
  ],
  'total': 3,
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
