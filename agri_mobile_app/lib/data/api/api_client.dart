import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

class ApiClient {
  ApiClient({Dio? dio, String? baseUrl})
      : dio = dio ??
            Dio(BaseOptions(
              baseUrl: baseUrl ?? businessApiBaseUrl,
              connectTimeout: const Duration(seconds: 10),
              receiveTimeout: const Duration(seconds: 60),
            ));

  final Dio dio;

  // Android 默认用于模拟器开发；真机由启动脚本或编译参数指定地址。
  static String get _localDevelopmentHost =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android
          ? '10.0.2.2'
          : '127.0.0.1';

  static String get businessApiBaseUrl {
    const configured = String.fromEnvironment('BUSINESS_API_BASE_URL',
        defaultValue: String.fromEnvironment('API_BASE_URL'));
    return configured.isNotEmpty
        ? configured
        : 'http://$_localDevelopmentHost:9876/api/v2';
  }

  static String get agentApiBaseUrl {
    const configured = String.fromEnvironment('AGENT_API_BASE_URL');
    return configured.isNotEmpty
        ? configured
        : 'http://$_localDevelopmentHost:8000/api/v2';
  }

  String get baseUrl => dio.options.baseUrl;

  void setAccessToken(String? token) {
    if (token == null || token.isEmpty) {
      dio.options.headers.remove('Authorization');
      return;
    }
    dio.options.headers['Authorization'] = 'Bearer $token';
  }

  Future<Response<dynamic>> get(String path, {Map<String, dynamic>? query}) {
    return dio.get(path, queryParameters: _compact(query));
  }

  Future<Response<dynamic>> post(
    String path, {
    Object? data,
    Map<String, dynamic>? query,
    Map<String, dynamic>? headers,
    ResponseType? responseType,
  }) {
    return dio.post(
      path,
      data: data,
      queryParameters: _compact(query),
      options: headers == null && responseType == null
          ? null
          : Options(headers: headers, responseType: responseType),
    );
  }

  Future<Response<dynamic>> put(String path, {Object? data}) {
    return dio.put(path, data: data);
  }

  Future<Response<dynamic>> patch(String path, {Object? data}) {
    return dio.patch(path, data: data);
  }

  Future<Response<dynamic>> delete(String path) {
    return dio.delete(path);
  }

  Future<bool> health() async {
    final response = await dio.get('/health');
    final statusCode = response.statusCode;
    return statusCode != null && statusCode >= 200 && statusCode < 300;
  }

  Future<Map<String, dynamic>> getMap(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    return asMap((await get(path, query: query)).data);
  }

  Future<List<dynamic>> getList(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    return asList((await get(path, query: query)).data);
  }

  Future<List<dynamic>> getItems(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    final data = await getMap(path, query: query);
    return asList(data['items']);
  }

  Future<Map<String, dynamic>> getAllPages(
    String path, {
    Map<String, dynamic>? query,
  }) async {
    const pageSize = 100;
    final items = <dynamic>[];
    var page = 1;
    while (true) {
      final data = await getMap(path, query: {
        ...?query,
        'page': page,
        'page_size': pageSize,
      });
      final batch = asList(data['items']);
      items.addAll(batch);
      final total = (data['total'] as num?)?.toInt() ?? items.length;
      if (items.length >= total || batch.isEmpty) {
        return {'items': items, 'total': total};
      }
      page += 1;
    }
  }

  Future<Map<String, dynamic>> postMap(
    String path, {
    Object? data,
    Map<String, dynamic>? query,
    Map<String, dynamic>? headers,
  }) async {
    return asMap(
      (await post(path, data: data, query: query, headers: headers)).data,
    );
  }

  Future<Map<String, dynamic>> putMap(String path, {Object? data}) async {
    return asMap((await put(path, data: data)).data);
  }

  Future<Map<String, dynamic>> patchMap(String path, {Object? data}) async {
    return asMap((await patch(path, data: data)).data);
  }

  static Map<String, dynamic> asMap(Object? data) {
    if (data is Map<String, dynamic>) return data;
    if (data is Map) return Map<String, dynamic>.from(data);
    throw StateError('接口响应不是对象: ${data.runtimeType}');
  }

  static List<dynamic> asList(Object? data) {
    if (data is List<dynamic>) return data;
    if (data is List) return List<dynamic>.from(data);
    throw StateError('接口响应不是列表: ${data.runtimeType}');
  }

  static String userMessageFor(Object error) {
    if (error is DioException) {
      if (error.response?.statusCode == 401) {
        return '登录已过期，请重新登录';
      }
      if (error.type == DioExceptionType.connectionError ||
          error.type == DioExceptionType.connectionTimeout ||
          error.type == DioExceptionType.receiveTimeout) {
        return '无法连接服务器，请确认后端已启动';
      }
      final detail = error.response?.data is Map
          ? (error.response!.data as Map)['detail']
          : null;
      final errors = detail is List
          ? detail
          : detail is Map && detail['meta'] is Map
              ? (detail['meta'] as Map)['errors']
              : null;
      if (errors is List && errors.isNotEmpty) {
        const labels = {
          'cycle_id': '关联茬口',
          'crop_template_id': '作物模板',
          'operation_type': '作业类型',
          'worker_id': '工人',
          'worker_name': '工人姓名',
          'name': '名称',
          'amount': '金额',
          'quantity': '数量',
          'unit_price': '单价',
          'paid_amount': '已付金额',
          'category': '分类',
          'stages': '生长阶段',
          'duration_days': '阶段天数',
          'record_date': '记账日期',
          'work_date': '作业日期',
          'start_date': '开始日期',
        };
        final messages = errors.whereType<Map>().map((item) {
          final location = item['loc'];
          final fields =
              location is List ? location.map((v) => '$v') : <String>[];
          final field = fields.where(labels.containsKey).lastOrNull;
          final label = labels[field] ?? '填写内容';
          return item['type'] == 'missing' ? '请填写$label' : '$label无效，请检查后重试';
        }).toSet();
        if (messages.isNotEmpty) return messages.join('；');
      }
      if (detail is Map && '${detail['message'] ?? ''}'.trim().isNotEmpty) {
        return '${detail['message']}';
      }
      if (detail is String && detail.trim().isNotEmpty) return detail;
    }
    if (error is UnsupportedApiException) return error.message;
    return '请求失败，请稍后重试';
  }

  static Map<String, dynamic>? _compact(Map<String, dynamic>? data) {
    if (data == null) return null;
    return Map<String, dynamic>.from(data)
      ..removeWhere((_, value) => value == null);
  }
}

class UnsupportedApiException implements Exception {
  const UnsupportedApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
