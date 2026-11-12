import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import '../core/api_client.dart';
import '../models/quiz_models.dart';

/// Server trả 200 nhưng body không phải JSON của API này (BASE_URL trỏ sai, cổng captive...).
class QuizFormatException implements Exception {
  const QuizFormatException([this.message = 'Máy chủ trả về dữ liệu không đúng định dạng.']);
  final String message;
}

/// Quiz: tạo từ một bản tóm tắt, mở ra làm và nộp điểm (docs/API.md, SPEC 5.4).
///
/// Quyền sở hữu do server kiểm tra qua bản tóm tắt cha, nên mọi id của người khác
/// về `NOT_FOUND` (404) — app chỉ việc đưa thông điệp tiếng Việt của server lên màn hình.
class QuizProvider extends ChangeNotifier {
  static const String _offlineMessage =
      'Chưa thể kết nối tới máy chủ. Vui lòng kiểm tra lại mạng.';
  static const String _formatMessage =
      'Máy chủ trả về dữ liệu không đúng định dạng.';

  /// Server giờ chỉ thử `GEMINI_MAX_RETRY`+1 = 2 lần với SDK không còn retry ngầm,
  /// tức trần thật của một lần tạo quiz là 2 x `GEMINI_QUIZ_TIMEOUT_SECONDS` (30s) = 60s
  /// cộng ghi DB. 90s để đủ chỗ cho cổ chai mạng mà không bắt người dùng ngồi nhìn
  /// nút "Đang tạo quiz" khi server đã bỏ từ lâu.
  static const Duration _generationTimeout = Duration(seconds: 90);

  final ApiClient _apiClient = ApiClient();

  bool _isCreating = false;
  String? _errorMessage;

  /// Đang chờ máy chủ sinh quiz: màn hình khoá nút để không đốt thêm lượt.
  bool get isCreating => _isCreating;
  String? get errorMessage => _errorMessage;

  void clearError() {
    if (_errorMessage == null) return;
    _errorMessage = null;
    notifyListeners();
  }

  /// `POST /summaries/{id}/quizzes` — tốn 1 lượt quiz và một lời gọi Gemini.
  Future<Quiz?> createQuiz(int summaryId) async {
    _isCreating = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final data = _unwrap(await _apiClient.dio.post(
        '/api/v1/summaries/$summaryId/quizzes',
        options: Options(receiveTimeout: _generationTimeout, sendTimeout: _generationTimeout),
      ));
      return Quiz.fromJson(data);
    } on DioException catch (e) {
      _errorMessage = _messageOf(e, 'Không tạo được quiz. Vui lòng thử lại.');
      return null;
    } on QuizFormatException catch (e) {
      _errorMessage = e.message;
      return null;
    } catch (_) {
      // Parse hỏng là TypeError/FormatException chứ không phải DioException.
      _errorMessage = _formatMessage;
      return null;
    } finally {
      _isCreating = false;
      notifyListeners();
    }
  }

  /// `GET /summaries/{id}/quizzes` — danh sách quiz đã có, không trừ lượt.
  Future<List<QuizListItem>> loadQuizzes(int summaryId) async {
    try {
      final data = _unwrap(await _apiClient.dio.get('/api/v1/summaries/$summaryId/quizzes'));
      final raw = data['items'];
      if (raw is! List) return const <QuizListItem>[];
      return raw
          .whereType<Map<dynamic, dynamic>>()
          .map((json) => QuizListItem.fromJson(json.cast<String, dynamic>()))
          .toList(growable: false);
    } on DioException catch (e) {
      _errorMessage = _messageOf(e, 'Không tải được danh sách quiz.');
      return const <QuizListItem>[];
    } on QuizFormatException catch (e) {
      _errorMessage = e.message;
      return const <QuizListItem>[];
    } catch (_) {
      _errorMessage = _formatMessage;
      return const <QuizListItem>[];
    }
  }

  /// `GET /quizzes/{id}` — mở một quiz đã có để làm lại, không tốn lượt.
  Future<Quiz?> openQuiz(int quizId) async {
    try {
      return Quiz.fromJson(_unwrap(await _apiClient.dio.get('/api/v1/quizzes/$quizId')));
    } on DioException catch (e) {
      _errorMessage = _messageOf(e, 'Không mở được quiz này.');
      return null;
    } on QuizFormatException catch (e) {
      _errorMessage = e.message;
      return null;
    } catch (_) {
      _errorMessage = _formatMessage;
      return null;
    }
  }

  /// `POST /quizzes/{id}/attempts` — server tự chấm, app chỉ gửi index đã chọn.
  /// Mảng `answers` bắt buộc đủ độ dài, câu bỏ trống gửi `null`.
  Future<AttemptResult?> submitAnswers({
    required int quizId,
    required List<int?> answers,
  }) async {
    _errorMessage = null;

    try {
      final data = _unwrap(await _apiClient.dio.post(
        '/api/v1/quizzes/$quizId/attempts',
        data: <String, dynamic>{'answers': answers},
      ));
      return AttemptResult.fromJson(data);
    } on DioException catch (e) {
      _errorMessage = _messageOf(e, 'Không nộp được bài. Vui lòng thử lại.');
      return null;
    } on QuizFormatException catch (e) {
      _errorMessage = e.message;
      return null;
    } catch (_) {
      _errorMessage = _formatMessage;
      return null;
    }
  }

  /// `GET /quizzes/{id}/attempts` — điểm các lần làm trước, mới nhất trước,
  /// cho mục "Các lần làm trước" ở màn kết quả. Phần này chỉ là phụ nên lỗi
  /// trả danh sách rỗng để ẩn mục đi; **không** đặt `errorMessage` vì màn kết
  /// quả không lắng nghe nó và thông báo cũ sẽ lèo sang hành động kế tiếp.
  Future<List<AttemptHistoryItem>> loadAttempts(int quizId) async {
    try {
      final data = _unwrap(await _apiClient.dio.get('/api/v1/quizzes/$quizId/attempts'));
      final raw = data['items'];
      if (raw is! List) return const <AttemptHistoryItem>[];
      return raw
          .whereType<Map<dynamic, dynamic>>()
          .map((json) => AttemptHistoryItem.fromJson(json.cast<String, dynamic>()))
          .toList(growable: false);
    } on DioException {
      return const <AttemptHistoryItem>[];
    } on QuizFormatException {
      return const <AttemptHistoryItem>[];
    } catch (_) {
      return const <AttemptHistoryItem>[];
    }
  }

  Map<String, dynamic> _unwrap(Response<dynamic> response) {
    final body = response.data;
    if (body is! Map) throw const QuizFormatException();
    final data = body['data'];
    if (data is! Map) throw const QuizFormatException();
    return data.cast<String, dynamic>();
  }

  /// Ưu tiên đúng thông điệp tiếng Việt của server: "hết lượt quiz", "quiz không tồn tại"
  /// và "mất mạng" là ba chuyện khác nhau — gộp lại thì người dùng không biết làm gì tiếp.
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
