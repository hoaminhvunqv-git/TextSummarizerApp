import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

class StorageService {
  static final StorageService _instance = StorageService._internal();
  factory StorageService() => _instance;
  StorageService._internal();

  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  static const String _deviceIdKey = 'device_id';
  static const String _tokenKey = 'auth_token';

  String? _cachedDeviceId;

  /// Sau proxy (Render) hai request song song cùng đi qua interceptor. Nếu cache
  /// *kết quả* thì cả hai thấy null và mỗi bên sinh một UUID v4 khác nhau — lịch sử
  /// và quota của thiết bị bị chia làm hai. Cache chính cái Future đang chạy.
  Future<String>? _deviceIdFuture;

  /// Lấy Device_ID duy nhất của thiết bị (UUID v4).
  /// Nếu chưa có trong Secure Storage, tự động sinh mới và lưu lại.
  Future<String> getDeviceId() {
    final cached = _cachedDeviceId;
    if (cached != null) return Future.value(cached);
    return _deviceIdFuture ??= _readOrInitDeviceId();
  }

  Future<String> _readOrInitDeviceId() async {
    try {
      String? deviceId = await _storage.read(key: _deviceIdKey);
      if (deviceId == null || deviceId.isEmpty) {
        deviceId = const Uuid().v4();
        await _storage.write(key: _deviceIdKey, value: deviceId);
      }
      _cachedDeviceId = deviceId;
      return deviceId;
    } finally {
      _deviceIdFuture = null;
    }
  }

  /// Lấy JWT token (nếu đã đăng nhập ở Giai đoạn 4)
  Future<String?> getToken() async {
    return await _storage.read(key: _tokenKey);
  }

  /// Lưu JWT token
  Future<void> saveToken(String token) async {
    await _storage.write(key: _tokenKey, value: token);
  }

  /// Xóa token khi đăng xuất
  Future<void> clearToken() async {
    await _storage.delete(key: _tokenKey);
  }
}
