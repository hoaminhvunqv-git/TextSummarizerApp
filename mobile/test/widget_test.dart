import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/main.dart';

void main() {
  testWidgets('App renders HomeView with basic elements', (WidgetTester tester) async {
    // Build app
    await tester.pumpWidget(const TextSummarizerApp());

    // Verify Title in AppBar
    expect(find.text('TextSummarizer AI'), findsOneWidget);

    // Verify 3 Ribbon Buttons
    expect(find.text('Dán chữ'), findsOneWidget);
    expect(find.text('Quét ảnh'), findsOneWidget);
    expect(find.text('Chọn tệp'), findsOneWidget);

    // Verify Primary Action Button
    expect(find.text('Tóm tắt văn bản'), findsOneWidget);
  });
}
