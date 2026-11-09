import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:dio/dio.dart';
import 'package:http_parser/http_parser.dart';
import 'package:image_picker/image_picker.dart';
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

  int unlockCharsFor(String length) =>
      AppConstants.lengthUnlockChars[length] ?? AppConstants.minChars;

  bool isLengthUnlocked(String length) => charCount >= unlockCharsFor(length);

  /// Số ký tự bản gốc còn thiếu để mở khoá một mốc tóm tắt
  int missingCharsFor(String length) {
    final int missing = unlockCharsFor(length) - charCount;
    return missing > 0 ? missing : 0;
  }

  bool get canSubmit => isValidLength && isLengthUnlocked(_selectedLength);

  SummaryProvider() {
    textController.addListener(() {
      // Văn bản bị xoá bớt có thể khiến mốc đang chọn bị khoá lại
      if (!isLengthUnlocked(_selectedLength)) {
        _selectedLength = 'short';
      }
      notifyListeners();
    });
  }

  void setSelectedLength(String length) {
    if (!isLengthUnlocked(length)) return;
    if (_selectedLength != length) {
      _selectedLength = length;
      notifyListeners();
    }
  }

  /// Dán văn bản từ Clipboard vào ô soạn thảo, trả về true nếu dán thành công
  Future<bool> pasteFromClipboard() async {
    final clipboardData = await Clipboard.getData(Clipboard.kTextPlain);
    if (clipboardData != null && clipboardData.text != null && clipboardData.text!.trim().isNotEmpty) {
      textController.text = clipboardData.text!;
      textController.selection = TextSelection.fromPosition(
        TextPosition(offset: textController.text.length),
      );
      notifyListeners();
      return true;
    }
    return false;
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

  /// Trích xuất văn bản từ file (TXT/DOCX/PDF)
  Future<void> extractFile() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['txt', 'docx', 'pdf'],
        allowMultiple: false,
      );

      if (result == null || result.files.isEmpty) {
        return; // User cancelled
      }

      final file = result.files.first;
      final fileName = file.name.toLowerCase();
      
      // Check extension
      if (!fileName.endsWith('.txt') && !fileName.endsWith('.docx') && !fileName.endsWith('.pdf')) {
        _errorMessage = 'Chỉ hỗ trợ file .txt, .docx, .pdf';
        notifyListeners();
        return;
      }

      _isLoading = true;
      _errorMessage = null;
      notifyListeners();

      // Create multipart form data
      final formData = FormData.fromMap({
        'file': MultipartFile.fromBytes(
          file.bytes!,
          filename: file.name,
        ),
      });

      final response = await _apiClient.dio.post(
        '/api/v1/files/extract',
        data: formData,
      );

      if (response.statusCode == 200) {
        final data = response.data['data'] as Map<String, dynamic>;
        final extractedText = data['text'] as String;
        setText(extractedText);
      } else {
        _errorMessage = response.data['message'] ?? 'Không thể trích xuất văn bản từ file.';
      }
    } on DioException catch (e) {
      if (e.response != null) {
        final errorData = e.response!.data;
        if (errorData is Map<String, dynamic>) {
          _errorMessage = errorData['message'] ?? 'Lỗi khi trích xuất file.';
        } else {
          _errorMessage = 'Lỗi khi trích xuất file.';
        }
      } else {
        _errorMessage = 'Không thể kết nối tới máy chủ. Vui lòng kiểm tra lại mạng.';
      }
    } catch (e) {
      _errorMessage = 'Đã có lỗi xảy ra khi trích xuất file.';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Nhận diện văn bản từ ảnh (OCR) bằng Gemini Vision API
  Future<void> recognizeText(ImageSource source) async {
    try {
      final ImagePicker picker = ImagePicker();
      final XFile? image = await picker.pickImage(source: source);

      if (image == null) {
        return; // User cancelled
      }

      _isLoading = true;
      _errorMessage = null;
      notifyListeners();

      // Đọc file ảnh thành bytes
      final imageBytes = await image.readAsBytes();
      
      // Tạo multipart form data
      final formData = FormData.fromMap({
        'image': MultipartFile.fromBytes(
          imageBytes,
          filename: image.name,
          contentType: MediaType.parse(_getMimeType(image.path)),
        ),
      });

      // Gọi API OCR
      final response = await _apiClient.dio.post(
        '/api/v1/ocr',
        data: formData,
      );

      if (response.statusCode == 200) {
        final data = response.data['data'] as Map<String, dynamic>;
        final extractedText = data['text'] as String;
        setText(extractedText);
      } else {
        _errorMessage = response.data['message'] ?? 'Không thể trích xuất văn bản từ ảnh.';
      }
    } on DioException catch (e) {
      if (e.response != null) {
        final errorData = e.response!.data;
        if (errorData is Map<String, dynamic>) {
          _errorMessage = errorData['message'] ?? 'Lỗi khi nhận diện văn bản từ ảnh.';
        } else {
          _errorMessage = 'Lỗi khi nhận diện văn bản từ ảnh.';
        }
      } else {
        _errorMessage = 'Không thể kết nối tới máy chủ. Vui lòng kiểm tra lại mạng.';
      }
    } catch (e) {
      _errorMessage = 'Đã có lỗi xảy ra khi nhận diện văn bản từ ảnh.';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Lấy MIME type từ đường dẫn file
  String _getMimeType(String path) {
    final extension = path.toLowerCase().split('.').last;
    switch (extension) {
      case 'jpg':
      case 'jpeg':
        return 'image/jpeg';
      case 'png':
        return 'image/png';
      case 'webp':
        return 'image/webp';
      default:
        return 'image/jpeg';
    }
  }

  /// Bắt đầu gửi yêu cầu tóm tắt
  Future<void> summarize() async {
    if (!canSubmit || _isLoading) return;

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
