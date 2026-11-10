import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/models/quiz_models.dart';

/// Payload chép theo đúng cấu trúc backend trả về trên Neon thật (smoke 2026-11-10):
/// `POST /summaries/{id}/quizzes` -> quiz + `usage`, `POST /quizzes/{id}/attempts` -> 201.
/// Test giữ cho tên khóa phía Dart không lệch khỏi API.md — cùng kiểu lỗi từng vấp
/// với `length` / `selected_length`.
void main() {
  Map<String, dynamic> question(int position, int correctIndex) => <String, dynamic>{
        'id': 30 + position,
        'position': position,
        'question': 'Câu $position có dấu tiếng Việt?',
        'options': <String>['Đáp án A', 'Đáp án B', 'Đáp án C', 'Đáp án D'],
        'correct_index': correctIndex,
        'explanation': 'Giải thích cho câu $position.',
      };

  final quizPayload = <String, dynamic>{
    'id': 4,
    'summary_id': 13,
    'question_count': 3,
    'language': 'vi',
    'created_at': '2026-11-10T20:55:36+07:00',
    'questions': <Object>[
      question(1, 1),
      question(2, 3),
      question(3, 1),
    ],
    'usage': <String, dynamic>{'summary_remaining': 19, 'quiz_remaining': 19},
  };

  group('Quiz.fromJson', () {
    test('đọc đủ các khóa snake_case của một quiz', () {
      final quiz = Quiz.fromJson(quizPayload);

      expect(quiz.id, 4);
      expect(quiz.summaryId, 13);
      expect(quiz.language, 'vi');
      expect(quiz.questions.length, 3);
      expect(quiz.quizRemaining, 19);
    });

    test('giữ nguyên thứ tự câu hỏi và đáp án đã xáo trộn của server', () {
      final quiz = Quiz.fromJson(quizPayload);

      // Server đã xáo đáp án và tính lại correct_index; app xáo lần nữa là lệch đáp án.
      expect(quiz.questions.map((q) => q.position).toList(), <int>[1, 2, 3]);
      expect(quiz.questions.map((q) => q.correctIndex).toList(), <int>[1, 3, 1]);
      expect(quiz.questions.first.options.length, 4);
      expect(quiz.questions.first.question, 'Câu 1 có dấu tiếng Việt?');
    });

    test('created_at +07:00 giữ đúng thời điểm tuyệt đối', () {
      expect(
        Quiz.fromJson(quizPayload).createdAt.toUtc(),
        DateTime.utc(2026, 11, 10, 13, 55, 36),
      );
    });

    test('GET /quizzes/{id} không có usage thì quizRemaining vẫn đọc được', () {
      final payload = Map<String, dynamic>.of(quizPayload)..remove('usage');
      final quiz = Quiz.fromJson(payload);

      expect(quiz.quizRemaining, isNull);
      expect(quiz.questions.length, 3);
    });

    test('questions khuyết thành danh sách rỗng thay vì crash', () {
      final quiz = Quiz.fromJson(const <String, dynamic>{
        'id': 5,
        'summary_id': 13,
        'language': 'vi',
        'created_at': '2026-11-10T20:55:36+07:00',
      });

      expect(quiz.questions, isEmpty);
      expect(quiz.id, 5);
    });
  });

  group('QuizQuestion.isCorrect', () {
    final item = QuizQuestion.fromJson(question(1, 1));

    test('trùng correct_index là đúng', () {
      expect(item.isCorrect(1), isTrue);
      expect(item.isCorrect(0), isFalse);
      expect(item.isCorrect(3), isFalse);
    });

    test('bỏ trống tính là sai, giống server', () {
      expect(item.isCorrect(null), isFalse);
    });
  });

  group('QuizListItem.fromJson', () {
    test('đọc dòng danh sách không kèm câu hỏi', () {
      final item = QuizListItem.fromJson(const <String, dynamic>{
        'id': 4,
        'summary_id': 13,
        'question_count': 9,
        'language': 'vi',
        'created_at': '2026-11-10T20:55:36+07:00',
      });

      expect(item.id, 4);
      expect(item.questionCount, 9);
      expect(item.createdAt.toUtc(), DateTime.utc(2026, 11, 10, 13, 55, 36));
    });
  });

  group('AttemptResult.fromJson', () {
    final payload = <String, dynamic>{
      'attempt_id': 1,
      'score': 8.9,
      'correct_count': 8,
      'total_count': 9,
      'results': <Object>[
        <String, dynamic>{
          'position': 1,
          'selected': null,
          'correct_index': 1,
          'is_correct': false,
        },
        <String, dynamic>{
          'position': 2,
          'selected': 3,
          'correct_index': 3,
          'is_correct': true,
        },
      ],
      'submitted_at': '2026-11-10T20:55:36+07:00',
    };

    test('đọc điểm server chấm và từng kết quả', () {
      final result = AttemptResult.fromJson(payload);

      expect(result.attemptId, 1);
      expect(result.score, 8.9);
      expect(result.correctCount, 8);
      expect(result.totalCount, 9);
      expect(result.results.length, 2);
      expect(result.submittedAt.toUtc(), DateTime.utc(2026, 11, 10, 13, 55, 36));
    });

    test('câu bỏ trống vẫn là null, không thành 0', () {
      final skipped = AttemptResult.fromJson(payload).results.first;

      expect(skipped.selected, isNull);
      expect(skipped.isCorrect, isFalse);
      expect(skipped.correctIndex, 1);
    });

    test('điểm tròn vẫn đọc được khi JSON là số nguyên', () {
      final perfect = AttemptResult.fromJson(
        Map<String, dynamic>.of(payload)..['score'] = 10,
      );

      expect(perfect.score, 10.0);
    });
  });
}
