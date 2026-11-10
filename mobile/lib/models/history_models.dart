/// Model cho hai response của API lịch sử (docs/API.md: GET /summaries, GET /summaries/{id}).
class HistoryItem {
  const HistoryItem({
    required this.id,
    required this.title,
    required this.description,
    required this.language,
    required this.source,
    required this.createdAt,
  });

  final int id;
  final String title;
  final String description;
  final String language;
  final String source;
  final DateTime createdAt;

  factory HistoryItem.fromJson(Map<String, dynamic> json) => HistoryItem(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        description: json['description'] as String? ?? '',
        language: json['language'] as String? ?? 'vi',
        source: json['source'] as String? ?? 'gemini',
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}

class SummaryDetail {
  const SummaryDetail({
    required this.id,
    required this.title,
    required this.description,
    required this.summary,
    required this.originalText,
    required this.originalLength,
    required this.language,
    required this.source,
    required this.createdAt,
  });

  final int id;
  final String title;
  final String description;
  final String summary;
  final String originalText;
  final int originalLength;
  final String language;
  final String source;
  final DateTime createdAt;

  factory SummaryDetail.fromJson(Map<String, dynamic> json) => SummaryDetail(
        id: json['id'] as int,
        title: json['title'] as String? ?? '',
        description: json['description'] as String? ?? '',
        summary: json['summary'] as String? ?? '',
        originalText: json['original_text'] as String? ?? '',
        originalLength: json['original_length'] as int? ?? 0,
        language: json['language'] as String? ?? 'vi',
        source: json['source'] as String? ?? 'gemini',
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
