import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/main.dart';

void main() {
  testWidgets('App renders HomeView with basic elements and new UI updates', (WidgetTester tester) async {
    // Build app
    await tester.pumpWidget(const TextSummarizerApp());

    // 1. Verify Title in AppBar
    expect(find.text('TextSummarizer AI'), findsOneWidget);

    // 2. Verify Language Support Subtitle
    expect(find.text('Hỗ trợ tóm tắt văn bản Tiếng Việt & Tiếng Anh'), findsOneWidget);

    // 3. Verify 3 Ribbon Buttons
    expect(find.text('Dán chữ'), findsOneWidget);
    expect(find.text('Quét ảnh'), findsOneWidget);
    expect(find.text('Chọn tệp'), findsOneWidget);

    // 4. Verify Length Selector with new label 'Dài'
    expect(find.text('Ngắn'), findsOneWidget);
    expect(find.text('Vừa'), findsOneWidget);
    expect(find.text('Dài'), findsOneWidget);

    // 5. Verify Primary Action Button
    expect(find.text('Tóm tắt văn bản'), findsOneWidget);

    // 6. Test tapping 'Dán chữ' triggers SnackBar when clipboard is empty
    await tester.tap(find.text('Dán chữ'));
    await tester.pump();
    expect(find.text('Bộ nhớ tạm chưa có nội dung văn bản'), findsOneWidget);
  });
}
