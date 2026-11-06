import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/constants.dart';
import '../core/api_client.dart';

class SummaryProvider extends ChangeNotifier {
  final TextEditingController textController = TextEditingController();
  final ApiClient _apiClient = ApiClient();

  String _selectedLength = 'medium'; // short | medium | long
  bool _isLoading = false;
  String? _errorMessage;
  Map<String, dynamic>? _summaryResult;

  String get selectedLength => _selectedLength;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  Map<String, dynamic>? get summaryResult => _summaryResult;

  int get charCount => textController.text.trim().length;

  bool get isValidLength =>
      charCount >= AppConstants.minChars && charCount <= AppConstants.maxChars;

  SummaryProvider() {
    textController.addListener(() {
      notifyListeners();
    });
  }

  void setSelectedLength(String length) {
    if (_selectedLength != length) {
      _selectedLength = length;
      notifyListeners();
    }
  }

  /// Dán văn bản từ Clipboard vào ô soạn thảo
  Future<void> pasteFromClipboard() async {
    final clipboardData = await Clipboard.getData(Clipboard.kTextPlain);
    if (clipboardData != null && clipboardData.text != null) {
      textController.text = clipboardData.text!;
      notifyListeners();
    }
  }

  /// Xóa sạch văn bản
  void clearText() {
    textController.clear();
    _errorMessage = null;
    _summaryResult = null;
    notifyListeners();
  }

  /// Cập nhật nội dung văn bản (dùng khi OCR quét xong hoặc tải file)
  void setText(String newText) {
    textController.text = newText;
    notifyListeners();
  }

  /// Bắt đầu gửi yêu cầu tóm tắt
  Future<void> summarize() async {
    if (!isValidLength || _isLoading) return;

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiClient.dio.post(
        '/api/v1/summaries',
        data: {
          'text': textController.text.trim(),
          'length': _selectedLength,
        },
      );

      if (response.statusCode == 200 || response.statusCode == 201) {
        _summaryResult = response.data['data'] as Map<String, dynamic>;
      } else {
        _errorMessage = response.data['message'] ?? 'Không thể tóm tắt văn bản.';
      }
    } catch (e) {
      _errorMessage = 'Chưa thể kết nối tới máy chủ AI. Vui lòng kiểm tra lại mạng.';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    textController.dispose();
    super.dispose();
  }
}
