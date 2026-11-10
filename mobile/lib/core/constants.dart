import 'package:flutter/material.dart';

class AppConstants {
  // Màu sắc chủ đạo theo docs/SPEC.md mục 4
  static const Color primaryColor = Color(0xFF143C64);
  static const Color secondaryColor = Color(0xFF2D5A87);
  static const Color backgroundColor = Color(0xFFF4F6F9);
  static const Color cardColor = Color(0xFFFFFFFF);
  static const Color textPrimaryColor = Color(0xFF1A1A1A);
  static const Color textSecondaryColor = Color(0xFF6C757D);

  static const Color successColor = Color(0xFF28A745);
  static const Color errorColor = Color(0xFFDC3545);
  static const Color warningColor = Color(0xFFFFC107);

  // Cấu hình API và Version
  static const String appVersion = "1.0.0";

  // Mặc định là máy dev (cần adb reverse tcp:5000 tcp:5000 khi chạy trên máy thật cắm cáp).
  // Bản production build với: flutter build apk --release --dart-define=BASE_URL=https://<app>.onrender.com
  static const String defaultBaseUrl = String.fromEnvironment(
    'BASE_URL',
    defaultValue: 'http://127.0.0.1:5000',
  );

  // Quy định độ dài văn bản
  static const int minChars = 400;
  static const int maxChars = 30000;

  // Số ký tự tối thiểu của bản gốc để mở khoá từng mốc tóm tắt (docs/SPEC.md 5.1)
  static const Map<String, int> lengthUnlockChars = {
    'short': 400,
    'medium': 1000,
    'long': 2000,
  };
}
