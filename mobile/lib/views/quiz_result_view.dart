import 'package:flutter/material.dart';
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
  });

  final Quiz quiz;
  final AttemptResult result;
  final VoidCallback onRestart;

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
          child: ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            itemCount: result.results.length,
            separatorBuilder: (_, _) => const SizedBox(height: 10),
            itemBuilder: (context, index) {
              final item = result.results[index];
              // `results` và `questions` cùng độ dài vì server chấm đúng số câu của quiz.
              final question = index < quiz.questions.length ? quiz.questions[index] : null;
              return _ResultTile(
                item: item,
                question: question?.question ?? 'Câu ${item.position}',
                options: question?.options ?? const <String>[],
              );
            },
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
