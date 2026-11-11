import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../core/constants.dart';
import '../models/quiz_models.dart';

/// Màn kết quả: điểm do **máy chủ** chấm (thang 10) kèm recap từng câu.
///
/// App không tự cộng điểm ở đây — `AttemptResult` là response 201 của
/// `POST /quizzes/{id}/attempts` (SPEC 5.4: client không được tin điểm tự tính).
class QuizResultView extends StatelessWidget {
  const QuizResultView({
    super.key,
    required this.quiz,
    required this.result,
    required this.onRestart,
    this.pastAttempts = const <AttemptHistoryItem>[],
  });

  final Quiz quiz;
  final AttemptResult result;
  final VoidCallback onRestart;

  /// Các lần làm trước của quiz này (đã loại lượt vừa nộp); rỗng = ẩn mục.
  final List<AttemptHistoryItem> pastAttempts;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(16, 22, 16, 22),
          color: AppConstants.primaryColor,
          child: Column(
            children: [
              Text(
                result.score.toStringAsFixed(1),
                style: const TextStyle(
                  fontSize: 44,
                  height: 1.1,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              const Text('/10', style: TextStyle(fontSize: 13, color: Colors.white70)),
              const SizedBox(height: 10),
              Text(
                'Đúng ${result.correctCount}/${result.totalCount} câu',
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: Colors.white,
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            children: [
              for (var i = 0; i < result.results.length; i++) ...[
                // `results` và `questions` cùng độ dài vì server chấm đúng số câu của quiz.
                _ResultTile(
                  item: result.results[i],
                  question: i < quiz.questions.length
                      ? quiz.questions[i].question
                      : 'Câu ${result.results[i].position}',
                  options: i < quiz.questions.length
                      ? quiz.questions[i].options
                      : const <String>[],
                ),
                const SizedBox(height: 10),
              ],
              if (pastAttempts.isNotEmpty) ...[
                Text(
                  'Các lần làm trước',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Colors.grey.shade800,
                  ),
                ),
                const SizedBox(height: 8),
                for (final attempt in pastAttempts) ...[
                  _PastAttemptTile(attempt: attempt),
                  const SizedBox(height: 8),
                ],
              ],
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
          child: Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: onRestart,
                  icon: const Icon(Icons.refresh_rounded, size: 20),
                  label: const Text('Làm lại'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.icon(
                  style: FilledButton.styleFrom(backgroundColor: AppConstants.primaryColor),
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.check_rounded, size: 20),
                  label: const Text('Xong'),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _ResultTile extends StatelessWidget {
  const _ResultTile({required this.item, required this.question, required this.options});

  final QuestionResult item;
  final String question;
  final List<String> options;

  String _optionText(int index) =>
      index >= 0 && index < options.length ? '${optionLetter(index)}. ${options[index]}' : '';

  @override
  Widget build(BuildContext context) {
    final color = item.isCorrect ? AppConstants.successColor : AppConstants.errorColor;
    final chosen = item.selected;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  item.isCorrect ? Icons.check_circle_rounded : Icons.cancel_rounded,
                  size: 18,
                  color: color,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Câu ${item.position}. $question',
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, height: 1.45),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              chosen == null ? 'Bạn bỏ trống' : 'Bạn chọn: ${_optionText(chosen)}',
              style: TextStyle(fontSize: 13, color: Colors.grey.shade800),
            ),
            if (!item.isCorrect) ...[
              const SizedBox(height: 2),
              Text(
                'Đáp án đúng: ${_optionText(item.correctIndex)}',
                style: const TextStyle(fontSize: 13, color: AppConstants.successColor),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Một dòng lịch sử: điểm gần nhất nằm trên cùng vì server trả mới nhất trước.
class _PastAttemptTile extends StatelessWidget {
  const _PastAttemptTile({required this.attempt});

  final AttemptHistoryItem attempt;

  static final DateFormat _dateFormat = DateFormat('dd/MM/yyyy HH:mm');

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            Text(
              '${attempt.score.toStringAsFixed(1)}/10',
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                color: AppConstants.primaryColor,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Đúng ${attempt.correctCount}/${attempt.totalCount} câu',
                style: TextStyle(fontSize: 13, color: Colors.grey.shade700),
              ),
            ),
            Text(
              _dateFormat.format(attempt.submittedAt),
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
            ),
          ],
        ),
      ),
    );
  }
}
