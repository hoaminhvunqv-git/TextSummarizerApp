import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../core/api_client.dart';
import '../models/history_models.dart';

/// Server trả 200 nhưng không phải JSON của API này (BASE_URL trỏ sai, cổng captive...).
class HistoryFormatException implements Exception {
  const HistoryFormatException([this.message = 'Máy chủ trả về dữ liệu không đúng định dạng.']);
  final String message;
}

/// Lịch sử bản tóm tắt của chính thiết bị đang dùng app (docs/API.md, SPEC 5.7).
class HistoryProvider extends ChangeNotifier {
  static const int pageSize = 20;
  static const String _offlineMessage =
      'Chưa thể kết nối tới máy chủ. Vui lòng kiểm tra lại mạng.';

  final ApiClient _apiClient = ApiClient();

  final List<HistoryItem> _items = [];
  int _total = 0;
  int _page = 0;
  bool _isLoading = false;
  bool _hasMore = false;
  bool _loadedOnce = false;
  String? _errorMessage;

  List<HistoryItem> get items => List<HistoryItem>.unmodifiable(_items);
  int get total => _total;
  bool get isLoading => _isLoading;
  bool get hasMore => _hasMore;

  /// Chưa gọi request nào: màn hình hiện vòng tải chứ chưa thể kết luận "lịch sử trống".
  bool get isPristine => !_loadedOnce;
  String? get errorMessage => _errorMessage;

  Future<void> refresh() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final data = _unwrap(await _apiClient.dio.get(
        '/api/v1/summaries',
        queryParameters: const {'page': 1, 'limit': pageSize},
      ));
      _items
        ..clear()
        ..addAll(_parseItems(data['items']));
      _total = (data['total'] as num?)?.toInt() ?? _items.length;
      _page = 1;
      _hasMore = _items.length < _total;
    } on DioException catch (e) {
      _errorMessage = _messageOf(e, 'Không tải được lịch sử. Vui lòng thử lại.');
    } on HistoryFormatException catch (e) {
      _errorMessage = e.message;
    } finally {
      _isLoading = false;
      _loadedOnce = true;
      notifyListeners();
    }
  }

  Future<void> loadMore() async {
    if (_isLoading || !_hasMore) return;

    _isLoading = true;
    notifyListeners();

    try {
      final data = _unwrap(await _apiClient.dio.get(
        '/api/v1/summaries',
        queryParameters: {'page': _page + 1, 'limit': pageSize},
      ));
      final pageItems = _parseItems(data['items']);
      _items.addAll(pageItems);
      _total = (data['total'] as num?)?.toInt() ?? _total;
      _page += 1;
      _hasMore = pageItems.isNotEmpty && _items.length < _total;
    } on DioException catch (e) {
      // Trang sau lỗi thì giữ nguyên những gì đang hiển thị, chỉ báo để người dùng thử lại.
      _errorMessage = _messageOf(e, 'Không tải thêm được lịch sử.');
    } on HistoryFormatException catch (e) {
      _errorMessage = e.message;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<SummaryDetail?> loadDetail(int id) async {
    _errorMessage = null;

    try {
      final data = _unwrap(await _apiClient.dio.get('/api/v1/summaries/$id'));
      return SummaryDetail.fromJson(data);
    } on DioException catch (e) {
      _errorMessage = _messageOf(e, 'Không mở được bản tóm tắt.');
      return null;
    } on HistoryFormatException catch (e) {
      _errorMessage = e.message;
      return null;
    }
  }

  /// Xóa một bản ghi; trả true khi server xác nhận đã xóa. Danh sách cập nhật tại chỗ,
  /// không gọi lại `refresh()` để người dùng không bị nhảy về trang 1.
  Future<bool> deleteItem(int id) async {
    _errorMessage = null;

    try {
      await _apiClient.dio.delete('/api/v1/summaries/$id');
      _items.removeWhere((item) => item.id == id);
      if (_total > 0) _total -= 1;
      _hasMore = _items.length < _total;
      notifyListeners();
      return true;
    } on DioException catch (e) {
      _errorMessage = _messageOf(e, 'Không xóa được bản tóm tắt.');
      notifyListeners();
      return false;
    }
  }

  Map<String, dynamic> _unwrap(Response<dynamic> response) {
    final body = response.data;
    if (body is! Map) throw const HistoryFormatException();
    final data = body['data'];
    if (data is! Map) throw const HistoryFormatException();
    return data.cast<String, dynamic>();
  }

  List<HistoryItem> _parseItems(Object? raw) {
    if (raw is! List) return const <HistoryItem>[];
    return raw
        .whereType<Map<dynamic, dynamic>>()
        .map((json) => HistoryItem.fromJson(json.cast<String, dynamic>()))
        .toList(growable: false);
  }

  /// Ưu tiên đúng thông điệp tiếng Việt của server: 404 "không tìm thấy" và 429 "hết lượt"
  /// là hai chuyện khác nhau, gộp lại thì người dùng không biết làm gì tiếp theo.
  String _messageOf(DioException e, String fallback) {
    if (e.type == DioExceptionType.connectionError || e.response == null) {
      return _offlineMessage;
    }
    final body = e.response!.data;
    if (body is Map) {
      final message = body['message'];
      if (message is String && message.isNotEmpty) return message;
    }
    return fallback;
  }
}
