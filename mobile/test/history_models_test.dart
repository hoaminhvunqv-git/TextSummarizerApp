import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/models/history_models.dart';

/// Payload chép nguyên văn cấu trúc backend trả về trên Neon thật (2026-11-10):
/// `GET /summaries` -> items 6 khóa, `GET /summaries/{id}` -> 10 khóa có `usage`.
/// Test này giữ cho tên khóa phía Dart không lệch khỏi API.md (kiểu lỗi từng vấp
/// với `length` / `selected_length`).
void main() {
  const listItem = <String, dynamic>{
    'id': 7,
    'title': 'Tiêu đề thật 1',
    'description': 'Mô tả thật có dấu tiếng Việt.',
    'language': 'vi',
    'source': 'gemini',
    'created_at': '2026-11-10T19:36:00+07:00',
  };

  const detailPayload = <String, dynamic>{
    'id': 7,
    'title': 'Tiêu đề thật 1',
    'description': 'Mô tả thật có dấu tiếng Việt.',
    'summary': 'Bản tóm tắt thật, một đoạn văn duy nhất.',
    'original_text': 'Văn bản gốc 501 ký tự, có dấu tiếng Việt.',
    'original_length': 501,
    'language': 'vi',
    'source': 'gemini',
    'created_at': '2026-11-10T19:36:00+07:00',
    'usage': {'summary_remaining': 19, 'quiz_remaining': 20},
  };

  group('HistoryItem.fromJson', () {
    test('đọc đủ sáu trường danh sách lịch sử', () {
      final item = HistoryItem.fromJson(listItem);

      expect(item.id, 7);
      expect(item.title, 'Tiêu đề thật 1');
      expect(item.description, 'Mô tả thật có dấu tiếng Việt.');
      expect(item.language, 'vi');
      expect(item.source, 'gemini');
    });

    test('created_at +07:00 giữ đúng thời điểm tuyệt đối', () {
      final item = HistoryItem.fromJson(listItem);

      expect(item.createdAt.toUtc(), DateTime.utc(2026, 11, 10, 12, 36));
    });
  });

  group('SummaryDetail.fromJson', () {
    test('đọc văn bản gốc theo đúng tên khóa snake_case', () {
      final detail = SummaryDetail.fromJson(detailPayload);

      expect(detail.originalText, 'Văn bản gốc 501 ký tự, có dấu tiếng Việt.');
      expect(detail.originalLength, 501);
      expect(detail.summary, 'Bản tóm tắt thật, một đoạn văn duy nhất.');
      expect(detail.createdAt.toUtc(), DateTime.utc(2026, 11, 10, 12, 36));
    });

    test('trường khuyết thành chuỗi rỗng thay vì crash', () {
      final detail = SummaryDetail.fromJson(const <String, dynamic>{
        'id': 8,
        'created_at': '2026-11-10T00:00:00+07:00',
      });

      expect(detail.id, 8);
      expect(detail.title, '');
      expect(detail.summary, '');
      expect(detail.originalText, '');
      expect(detail.originalLength, 0);
      expect(detail.language, 'vi');
      expect(detail.source, 'gemini');
    });
  });
}
