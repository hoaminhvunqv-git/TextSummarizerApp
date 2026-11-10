import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/models/quiz_models.dart';
import 'package:mobile/views/quiz_result_view.dart';
import 'package:mobile/views/quiz_view.dart';

/// Ba màn hình quiz kiểm được bằng widget test mà không cần gọi máy chủ:
/// màn làm bài (phản hồi tức thì tại máy) và màn kết quả (điểm server chấm,
/// ở đây đưa vào bằng `AttemptResult` tưởng trưng cho response 201 thật).
void main() {
  QuizQuestion buildQuestion(int position, int correctIndex) => QuizQuestion(
        id: 30 + position,
        position: position,
        question: 'Nội dung câu $position?',
        options: const <String>['Đáp án A', 'Đáp án B', 'Đáp án C', 'Đáp án D'],
        correctIndex: correctIndex,
        explanation: 'Giải thích cho câu $position.',
      );

  Quiz buildQuiz({int count = 3}) => Quiz(
        id: 4,
        summaryId: 13,
        language: 'vi',
        createdAt: DateTime.utc(2026, 11, 10, 13, 55, 36),
        questions: List<QuizQuestion>.generate(count, (i) => buildQuestion(i + 1, (i % 4 == 0) ? 1 : (i * 2) % 4)),
      );

  QuestionResult buildResult(int position, int? selected, int correctIndex) => QuestionResult(
        position: position,
        selected: selected,
        correctIndex: correctIndex,
        isCorrect: selected != null && selected == correctIndex,
      );

  Future<void> pumpQuiz(WidgetTester tester, Quiz quiz) async {
    await tester.pumpWidget(MaterialApp(home: QuizView(quiz: quiz)));
  }

  group('QuizView — màn làm bài', () {
    testWidgets('mở đầu hiển thị câu 1, bốn đáp án và chưa lộ đáp án đúng', (tester) async {
      await pumpQuiz(tester, buildQuiz());

      expect(find.text('Câu 1/3'), findsOneWidget);
      expect(find.text('Đã trả lời 0/3'), findsOneWidget);
      expect(find.text('Đáp án A'), findsOneWidget);
      expect(find.text('Đáp án D'), findsOneWidget);
      expect(find.text('Chính xác'), findsNothing);
      expect(find.text('Giải thích cho câu 1.'), findsNothing);
      expect(find.text('Nộp bài'), findsNothing);
    });

    testWidgets('chọn đúng đáp án báo "Chính xác" và hiện giải thích ngay', (tester) async {
      await pumpQuiz(tester, buildQuiz());

      await tester.tap(find.text('Đáp án B'));
      await tester.pump();

      expect(find.text('Chính xác'), findsOneWidget);
      expect(find.text('Giải thích cho câu 1.'), findsOneWidget);
      expect(find.text('Đã trả lời 1/3'), findsOneWidget);
      expect(find.text('Bỏ qua câu này'), findsNothing);
      expect(find.text('Câu tiếp theo'), findsOneWidget);
    });

    testWidgets('chọn sai nêu rõ đáp án đúng và khoá lại không cho đổi', (tester) async {
      await pumpQuiz(tester, buildQuiz());

      await tester.tap(find.text('Đáp án A'));
      await tester.pump();
      expect(find.text('Chưa đúng — đáp án đúng là B'), findsOneWidget);

      // Đáp án đã ghi vào mảng nộp đi, bấm thêm câu khác phải không đổi trạng thái.
      await tester.tap(find.text('Đáp án D'));
      await tester.pump();
      expect(find.text('Chưa đúng — đáp án đúng là B'), findsOneWidget);
      expect(find.text('Chính xác'), findsNothing);
      expect(find.text('Đã trả lời 1/3'), findsOneWidget);
    });

    testWidgets('bỏ trống vẫn mở giải thích nhưng không tính là đã trả lời', (tester) async {
      await pumpQuiz(tester, buildQuiz());

      await tester.tap(find.text('Bỏ qua câu này'));
      await tester.pump();

      expect(find.text('Bạn bỏ trống — đáp án đúng là B'), findsOneWidget);
      expect(find.text('Giải thích cho câu 1.'), findsOneWidget);
      expect(find.text('Đã trả lời 0/3'), findsOneWidget);
    });

    testWidgets('đi hết các câu thì nút cuối đổi thành "Nộp bài"', (tester) async {
      await pumpQuiz(tester, buildQuiz());

      for (int i = 0; i < 2; i++) {
        await tester.tap(find.text('Đáp án B'));
        await tester.pump();
        await tester.tap(find.text('Câu tiếp theo'));
        await tester.pump();
      }

      expect(find.text('Câu 3/3'), findsOneWidget);
      expect(find.text('Câu tiếp theo'), findsNothing);

      await tester.tap(find.text('Đáp án B'));
      await tester.pump();
      expect(find.text('Nộp bài'), findsOneWidget);
    });

    testWidgets('quiz rỗng không chia 0 lần', (tester) async {
      await pumpQuiz(tester, buildQuiz(count: 0));

      expect(find.text('Quiz này không có câu hỏi nào. Hãy tạo quiz mới.'), findsOneWidget);
      expect(find.textContaining('/0'), findsNothing);
    });
  });

  group('QuizResultView — màn kết quả', () {
    AttemptResult buildResult9() => AttemptResult(
          attemptId: 9,
          score: 8.9,
          correctCount: 8,
          totalCount: 9,
          results: <QuestionResult>[
            buildResult(1, null, 1),
            buildResult(2, 0, 3),
            buildResult(3, 1, 1),
          ],
          submittedAt: DateTime.utc(2026, 11, 10, 13, 55, 36),
        );

    Future<void> pumpResult(WidgetTester tester, {required VoidCallback onRestart}) async {
      await tester.pumpWidget(
        MaterialApp(
          home: QuizResultView(
            quiz: buildQuiz(count: 3),
            result: buildResult9(),
            onRestart: onRestart,
          ),
        ),
      );
    }

    testWidgets('hiển thị điểm thập phân của server trên thang 10', (tester) async {
      await pumpResult(tester, onRestart: () {});

      expect(find.text('8.9'), findsOneWidget);
      expect(find.text('/10'), findsOneWidget);
      expect(find.text('Đúng 8/9 câu'), findsOneWidget);
    });

    testWidgets('recap nêu rõ câu bỏ trống, câu sai và đáp án đúng', (tester) async {
      await pumpResult(tester, onRestart: () {});

      expect(find.text('Câu 1. Nội dung câu 1?'), findsOneWidget);
      expect(find.text('Bạn bỏ trống'), findsOneWidget);
      expect(find.text('Bạn chọn: A. Đáp án A'), findsOneWidget);
      expect(find.text('Đáp án đúng: D. Đáp án D'), findsOneWidget);
      // Chỉ hai câu sai (bỏ trống + chọn sai) mới có dòng "Đáp án đúng".
      expect(find.textContaining('Đáp án đúng:'), findsNWidgets(2));
    });

    testWidgets('nút Làm lại callback để màn cha xoá đáp án', (tester) async {
      var restarts = 0;
      await pumpResult(tester, onRestart: () => restarts++);

      await tester.tap(find.text('Làm lại'));
      await tester.pump();

      expect(restarts, 1);
    });
  });
}
