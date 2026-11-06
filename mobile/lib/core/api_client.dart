import 'dart:async';
import 'package:dio/dio.dart';
import 'constants.dart';
import 'storage_service.dart';

class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;

  late final Dio dio;
  final StorageService _storageService = StorageService();

  ApiClient._internal() {
    dio = Dio(
      BaseOptions(
        baseUrl: AppConstants.defaultBaseUrl,
        connectTimeout: const Duration(seconds: 60),
        receiveTimeout: const Duration(seconds: 60),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Tự động gắn X-Device-ID và X-App-Version theo SPEC 1 & API.md
          final deviceId = await _storageService.getDeviceId();
          options.headers['X-Device-ID'] = deviceId;
          options.headers['X-App-Version'] = AppConstants.appVersion;

          // Gắn Authorization Bearer token nếu đã có
          final token = await _storageService.getToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }

          return handler.next(options);
        },
        onError: (DioException error, handler) {
          // Chuẩn hóa thông điệp lỗi mạng/timeout
          return handler.next(error);
        },
      ),
    );
  }

  /// Thay đổi Base URL khi deploy Render hoặc test IP mạng nội bộ
  void updateBaseUrl(String newUrl) {
    dio.options.baseUrl = newUrl;
  }

  /// Gọi thử GET /health
  Future<bool> checkHealth() async {
    try {
      final response = await dio.get('/health');
      return response.statusCode == 200 && response.data['status'] == 'ok';
    } catch (_) {
      return false;
    }
  }

  /// Gọi thử GET /api/v1/config
  Future<Map<String, dynamic>?> getConfig() async {
    try {
      final response = await dio.get('/api/v1/config');
      if (response.statusCode == 200 && response.data['success'] == true) {
        return response.data['data'] as Map<String, dynamic>;
      }
      return null;
    } catch (_) {
      return null;
    }
  }
}
