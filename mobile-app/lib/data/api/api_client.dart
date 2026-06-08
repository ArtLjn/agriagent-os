import 'package:dio/dio.dart';

class ApiClient {
  ApiClient({Dio? dio})
      : dio = dio ??
            Dio(BaseOptions(
                baseUrl: const String.fromEnvironment('API_BASE_URL')));

  final Dio dio;

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
  }) {
    return dio.post(
      path,
      data: data,
      queryParameters: _compact(query),
      options: headers == null ? null : Options(headers: headers),
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

  static Map<String, dynamic>? _compact(Map<String, dynamic>? data) {
    if (data == null) return null;
    return Map<String, dynamic>.from(data)..removeWhere((_, value) => value == null);
  }
}
