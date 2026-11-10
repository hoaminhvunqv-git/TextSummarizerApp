/// Model cho nhóm endpoint quiz (docs/API.md): tạo/đọc quiz và nộp bài.
///
/// Tên khóa giữ nguyên snake_case như response thật của backend trên Neon
/// (2026-11-10) — cùng lý do với `history_models.dart`: hai key từng bị nhầm
/// `length` / `selected_length` nên ánh xạ phải có test giữ chân.
class QuizQuestion {
  const QuizQuestion({
    required this.id,
    required this.position,
    required this.question,
    required this.options,
    required this.correctIndex,
    required this.explanation,
  });

  final int id;

  /// Đánh từ 1 phía server, dùng để in "Câu 3/9".
  final int position;
  final String question;
  final List<String> options;

  /// Vị trí đáp án đúng **sau khi xáo trộn** (0–3). Server đã xáo nên app không được
  /// tự xáo lại, nếu không `correct_index` và đáp án hiển thị sẽ lệch nhau.
  final int correctIndex;
  final String explanation;

  factory QuizQuestion.fromJson(Map<String, dynamic> json) => QuizQuestion(
        id: _int(json['id']) ?? 0,
        position: _int(json['position']) ?? 0,
        question: json['question'] as String? ?? '',
        options: (json['options'] as List?)?.map((e) => '$e').toList(growable: false) ?? const <String>[],
        correctIndex: _int(json['correct_index']) ?? -1,
        explanation: json['explanation'] as String? ?? '',
      );

  /// Bỏ trống (`null`) tính là sai — đúng quy tắc `grade_quiz` của server (SPEC 5.4),
  /// để điểm tạm hiện trên máy và điểm server chấm không lệch nhau.
  bool isCorrect(int? selected) => selected != null && selected == correctIndex;
}

/// Response của `POST /summaries/{id}/quizzes` và `GET /quizzes/{id}` — hai shape
/// giống nhau, chỉ khác khối `usage` đi kèm ở lần tạo.
class Quiz {
  const Quiz({
    required this.id,
    required this.summaryId,
    required this.language,
    required this.createdAt,
    required this.questions,
    this.quizRemaining,
  });

  final int id;
  final int summaryId;
  final String language;
  final DateTime createdAt;

  /// Đã xếp theo `position` tăng dần kể từ lúc server ghi DB, app giữ nguyên thứ tự.
  final List<QuizQuestion> questions;

  /// `usage.quiz_remaining` — chỉ có khi vừa tạo quiz, dùng để cập nhật dòng lượt còn lại.
  final int? quizRemaining;

  factory Quiz.fromJson(Map<String, dynamic> json) => Quiz(
        id: _int(json['id']) ?? 0,
        summaryId: _int(json['summary_id']) ?? 0,
        language: json['language'] as String? ?? 'vi',
        createdAt: DateTime.parse(json['created_at'] as String),
        questions: _questions(json['questions']),
        quizRemaining: _int(_usage(json)?['quiz_remaining']),
      );
}

/// Một dòng trong `GET /summaries/{id}/quizzes`: đủ để mở quiz mà không giải mã câu hỏi.
class QuizListItem {
  const QuizListItem({
    required this.id,
    required this.questionCount,
    required this.language,
    required this.createdAt,
  });

  final int id;
  final int questionCount;
  final String language;
  final DateTime createdAt;

  factory QuizListItem.fromJson(Map<String, dynamic> json) => QuizListItem(
        id: _int(json['id']) ?? 0,
        questionCount: _int(json['question_count']) ?? 0,
        language: json['language'] as String? ?? 'vi',
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

/// Một câu trong `results` mà server trả về sau khi chấm.
class QuestionResult {
  const QuestionResult({
    required this.position,
    required this.selected,
    required this.correctIndex,
    required this.isCorrect,
  });

  final int position;

  /// `null` = câu đó bỏ trống.
  final int? selected;
  final int correctIndex;
  final bool isCorrect;

  factory QuestionResult.fromJson(Map<String, dynamic> json) => QuestionResult(
        position: _int(json['position']) ?? 0,
        selected: _int(json['selected']),
        correctIndex: _int(json['correct_index']) ?? -1,
        isCorrect: json['is_correct'] == true,
      );
}

/// Response 201 của `POST /quizzes/{id}/attempts`: điểm do **server** chấm.
class AttemptResult {
  const AttemptResult({
    required this.attemptId,
    required this.score,
    required this.correctCount,
    required this.totalCount,
    required this.results,
    required this.submittedAt,
  });

  final int attemptId;

  /// Thang 10, một chữ số thập phân.
  final double score;
  final int correctCount;
  final int totalCount;
  final List<QuestionResult> results;
  final DateTime submittedAt;

  factory AttemptResult.fromJson(Map<String, dynamic> json) {
    final raw = json['results'];
    return AttemptResult(
      attemptId: _int(json['attempt_id']) ?? 0,
      score: (json['score'] as num?)?.toDouble() ?? 0,
      correctCount: _int(json['correct_count']) ?? 0,
      totalCount: _int(json['total_count']) ?? 0,
      results: raw is List
          ? raw
              .whereType<Map<dynamic, dynamic>>()
              .map((e) => QuestionResult.fromJson(e.cast<String, dynamic>()))
              .toList(growable: false)
          : const <QuestionResult>[],
      submittedAt: DateTime.parse(json['submitted_at'] as String),
    );
  }
}

Map<String, dynamic>? _usage(Map<String, dynamic> json) {
  final usage = json['usage'];
  return usage is Map ? usage.cast<String, dynamic>() : null;
}

List<QuizQuestion> _questions(Object? raw) {
  if (raw is! List) return const <QuizQuestion>[];
  return raw
      .whereType<Map<dynamic, dynamic>>()
      .map((json) => QuizQuestion.fromJson(json.cast<String, dynamic>()))
      .toList(growable: false);
}

/// A–D theo thứ tự 0–3, khớp cách server lưu `correct_index`.
String optionLetter(int index) => String.fromCharCode(65 + index);

/// JSON số có thể sang Dart dưới dạng `int` hoặc `double` (`score` là `real`),
/// nên mọi số nguyên đều đi qua hàm này thay vì cast thẳng.
int? _int(Object? value) => value is num ? value.toInt() : null;
