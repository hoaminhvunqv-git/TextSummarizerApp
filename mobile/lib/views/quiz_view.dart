import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../core/constants.dart';
import '../models/quiz_models.dart';
import '../providers/quiz_provider.dart';
import 'quiz_result_view.dart';

/// Màn làm quiz: từng câu một, chọn A–D là biết đúng/sai ngay, cuối cùng nộp lên
/// máy chủ để lấy điểm chính thức (SPEC 5.4).
///
/// App chấm tại máy chỉ để có phản hồi tức thì; con số trên màn kết quả là điểm
/// server trả về, không phải điểm tự tính.
class QuizView extends StatefulWidget {
  const QuizView({super.key, required this.quiz});

  final Quiz quiz;

  @override
  State<QuizView> createState() => _QuizViewState();
}

class _QuizViewState extends State<QuizView> {
  /// Đáp án đã chọn cho từng câu; `null` = bỏ trống (server vẫn chấm, tính là sai).
  final List<int?> _answers = <int?>[];
  int _index = 0;
  bool _revealed = false;
  bool _isSubmitting = false;
  AttemptResult? _result;

  /// Các lần làm trước của quiz này (đã loại lượt vừa nộp); rỗng = lần đầu hoặc lỗi tải.
  List<AttemptHistoryItem> _pastAttempts = const <AttemptHistoryItem>[];

  Quiz get _quiz => widget.quiz;
  int get _total => _quiz.questions.length;

  @override
  void initState() {
    super.initState();
    _answers.addAll(List<int?>.filled(_total, null));
  }

  void _select(int optionIndex) {
    if (_revealed || _isSubmitting) return;
    _answers[_index] = optionIndex;
    setState(() => _revealed = true);
  }

  /// Bỏ trống là lựa chọn có chủ đích, không phải quên: vẫn mở phần giải thích để học.
  void _skip() {
    if (_revealed || _isSubmitting) return;
    _answers[_index] = null;
    setState(() => _revealed = true);
  }

  void _next() {
    if (_index + 1 < _total) {
      setState(() {
        _index += 1;
        _revealed = false;
      });
      return;
    }
    _submit();
  }

  Future<void> _submit() async {
    setState(() => _isSubmitting = true);
    final provider = context.read<QuizProvider>();
    final result = await provider.submitAnswers(
      quizId: _quiz.id,
      answers: List<int?>.of(_answers),
    );
    if (!mounted) return;
    setState(() => _isSubmitting = false);

    if (result == null) {
      // Giữ nguyên đáp án đã chọn: người dùng chỉ việc bấm lại, không phải làm từ đầu.
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text(provider.errorMessage ?? 'Không nộp được bài. Vui lòng thử lại.'),
            backgroundColor: AppConstants.errorColor,
          ),
        );
      return;
    }
    setState(() => _result = result);

    // Lịch sử chỉ là phần phụ: tải sau khi điểm đã hiện nên lỗi mạng chỉ làm
    // ẩn mục đi, không chặn màn kết quả (provider không đặt errorMessage).
    final attempts = await provider.loadAttempts(_quiz.id);
    if (!mounted) return;
    setState(() {
      _pastAttempts = attempts
          .where((attempt) => attempt.id != result.attemptId)
          .toList(growable: false);
    });
  }

  /// Làm lại tại chỗ: một lượt nộp mới là một dòng `quiz_attempts` và không tốn lượt quiz.
  void _restart() {
    setState(() {
      _result = null;
      _index = 0;
      _revealed = false;
      _isSubmitting = false;
      _answers
        ..clear()
        ..addAll(List<int?>.filled(_total, null));
    });
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    return Scaffold(
      appBar: AppBar(title: Text(result == null ? 'Làm quiz' : 'Kết quả')),
      body: result != null
          ? QuizResultView(
              quiz: _quiz,
              result: result,
              pastAttempts: _pastAttempts,
              onRestart: _restart,
            )
          : _buildQuestion(),
    );
  }

  Widget _buildQuestion() {
    final questions = _quiz.questions;
    if (questions.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Quiz này không có câu hỏi nào. Hãy tạo quiz mới.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    final question = questions[_index];
    final answered = _answers[_index];
    final isLast = _index + 1 == _total;

    return SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Câu ${question.position}/$_total',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                    ),
                    Text(
                      'Đã trả lời ${_answers.where((a) => a != null).length}/$_total',
                      style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: (_index + 1) / _total,
                    minHeight: 6,
                    backgroundColor: Colors.grey.shade200,
                    color: AppConstants.primaryColor,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    question.question,
                    style: const TextStyle(fontSize: 16, height: 1.5, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 16),
                  for (int i = 0; i < question.options.length; i++) ...[
                    _OptionTile(
                      letter: optionLetter(i),
                      text: question.options[i],
                      revealed: _revealed,
                      isSelected: answered == i,
                      isAnswer: question.correctIndex == i,
                      onTap: () => _select(i),
                    ),
                    const SizedBox(height: 8),
                  ],
                  if (_revealed) _ExplanationBox(question: question, answered: answered),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              children: [
                if (!_revealed)
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: _isSubmitting ? null : _skip,
                      child: const Text('Bỏ qua câu này'),
                    ),
                  ),
                if (_revealed || _isSubmitting)
                  FilledButton.icon(
                    onPressed: _isSubmitting ? null : _next,
                    style: FilledButton.styleFrom(
                      backgroundColor: AppConstants.primaryColor,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    icon: _isSubmitting
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white),
                          )
                        : Icon(
                            isLast ? Icons.fact_check_outlined : Icons.arrow_forward_rounded,
                            size: 20,
                          ),
                    label: Text(
                      _isSubmitting
                          ? 'Đang chấm...'
                          : isLast
                              ? 'Nộp bài'
                              : 'Câu tiếp theo',
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Hộp giải thích hiện sau khi chọn, kèm nhắc nếu người dùng bỏ trống câu đó.
class _ExplanationBox extends StatelessWidget {
  const _ExplanationBox({required this.question, required this.answered});

  final QuizQuestion question;
  final int? answered;

  @override
  Widget build(BuildContext context) {
    final correct = question.isCorrect(answered);
    final color = correct ? AppConstants.successColor : AppConstants.errorColor;
    final String headline;
    if (answered == null) {
      headline = 'Bạn bỏ trống — đáp án đúng là ${optionLetter(question.correctIndex)}';
    } else if (correct) {
      headline = 'Chính xác';
    } else {
      headline = 'Chưa đúng — đáp án đúng là ${optionLetter(question.correctIndex)}';
    }

    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.45)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                correct ? Icons.check_circle_rounded : Icons.cancel_rounded,
                size: 18,
                color: color,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  headline,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: color,
                    fontSize: 13.5,
                  ),
                ),
              ),
            ],
          ),
          if (question.explanation.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              question.explanation,
              style: const TextStyle(fontSize: 13.5, height: 1.5),
            ),
          ],
        ],
      ),
    );
  }
}

class _OptionTile extends StatelessWidget {
  const _OptionTile({
    required this.letter,
    required this.text,
    required this.revealed,
    required this.isSelected,
    required this.isAnswer,
    required this.onTap,
  });

  final String letter;
  final String text;
  final bool revealed;
  final bool isSelected;
  final bool isAnswer;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final Color borderColor;
    final Color background;
    if (!revealed) {
      borderColor = Colors.grey.shade300;
      background = AppConstants.cardColor;
    } else if (isAnswer) {
      borderColor = AppConstants.successColor;
      background = AppConstants.successColor.withValues(alpha: 0.08);
    } else if (isSelected) {
      borderColor = AppConstants.errorColor;
      background = AppConstants.errorColor.withValues(alpha: 0.08);
    } else {
      borderColor = Colors.grey.shade300;
      background = Colors.grey.shade100;
    }

    return Material(
      color: background,
      borderRadius: BorderRadius.circular(10),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        // Chọn xong là khoá: đáp án đã ghi vào `_answers`, đổi ý sẽ lệch với mảng nộp đi.
        onTap: revealed ? null : onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: borderColor, width: revealed ? 1.4 : 1),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 12,
                backgroundColor: borderColor,
                child: Text(
                  letter,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(text, style: const TextStyle(fontSize: 14.5, height: 1.45)),
              ),
              if (revealed && isSelected)
                Icon(
                  isAnswer ? Icons.check_circle_rounded : Icons.cancel_rounded,
                  size: 20,
                  color: isAnswer ? AppConstants.successColor : AppConstants.errorColor,
                ),
            ],
          ),
        ),
      ),
    );
  }
}
