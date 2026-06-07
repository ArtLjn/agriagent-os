import 'package:dio/dio.dart';

class ApiClient {
  ApiClient({Dio? dio})
      : dio = dio ??
            Dio(BaseOptions(
                baseUrl: const String.fromEnvironment('API_BASE_URL')));

  final Dio dio;

  Future<Response<dynamic>> get(String path, {Map<String, dynamic>? query}) {
    return dio.get(path, queryParameters: query);
  }

  Future<Response<dynamic>> post(String path, {Object? data}) {
    return dio.post(path, data: data);
  }
}
