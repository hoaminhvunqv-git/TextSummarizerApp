import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';
import '../core/constants.dart';
import '../models/history_models.dart';
import '../models/quiz_models.dart';
import '../providers/history_provider.dart';
import '../providers/quiz_provider.dart';
import 'quiz_view.dart';

/// Một bản tóm tắt đã lưu: nội dung, văn bản gốc, quiz và nút xóa
/// (docs/API.md: GET/DELETE /summaries/{id}, /summaries/{id}/quizzes).
class SummaryDetailView extends StatefulWidget {
  const SummaryDetailView({super.key, required this.summaryId});

  final int summaryId;

  @override
  State<SummaryDetailView> createState() => _SummaryDetailViewState();
}

class _SummaryDetailViewState extends State<SummaryDetailView> {
  static final DateFormat _dateFormat = DateFormat('dd/MM/yyyy HH:mm');

  SummaryDetail? _detail;
  String? _errorMessage;
  bool _isLoading = true;
  bool _showOriginal = false;

  List<QuizListItem> _quizzes = const <QuizListItem>[];
  bool _isLoadingQuizzes = false;

  /// Đang gọi máy chủ sinh quiz hoặc đang mở một quiz cũ — khoá nút để không đốt hai lượt.
  bool _isQuizBusy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    final provider = context.read<HistoryProvider>();
    final detail = await provider.loadDetail(widget.summaryId);
    if (!mounted) return;
    setState(() {
      _isLoading = false;
      _detail = detail;
      _errorMessage = detail == null ? provider.errorMessage : null;
    });
    if (detail != null) await _loadQuizzes();
  }

  Future<void> _loadQuizzes() async {
    setState(() => _isLoadingQuizzes = true);
    final quizzes = await context.read<QuizProvider>().loadQuizzes(widget.summaryId);
    if (!mounted) return;
    setState(() {
      _quizzes = quizzes;
      _isLoadingQuizzes = false;
    });
  }

  /// Tạo quiz mới tốn 1 lượt quiz và một lời gọi Gemini (~20–30s), nên báo lỗi
  /// bằng đúng thông điệp server trả: "hết lượt" khác "mất mạng" khác "văn bản quá ngắn".
  Future<void> _createQuiz() async {
    setState(() => _isQuizBusy = true);
    final provider = context.read<QuizProvider>();
    final quiz = await provider.createQuiz(widget.summaryId);
    if (!mounted) return;
    setState(() => _isQuizBusy = false);

    if (quiz == null) {
      _showQuizError(provider.errorMessage ?? 'Không tạo được quiz. Vui lòng thử lại.');
      return;
    }
    await _loadQuizzes();
    if (!mounted) return;
    await _open(quiz);
  }

  Future<void> _openExisting(QuizListItem item) async {
    setState(() => _isQuizBusy = true);
    final provider = context.read<QuizProvider>();
    final quiz = await provider.openQuiz(item.id);
    if (!mounted) return;
    setState(() => _isQuizBusy = false);

    if (quiz == null) {
      _showQuizError(provider.errorMessage ?? 'Không mở được quiz này.');
      return;
    }
    await _open(quiz);
  }

  Future<void> _open(Quiz quiz) async {
    await Navigator.push<void>(
      context,
      MaterialPageRoute(builder: (_) => QuizView(quiz: quiz)),
    );
    if (!mounted) return;
    await _loadQuizzes();
  }

  void _showQuizError(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(content: Text(message), backgroundColor: AppConstants.errorColor),
      );
  }

  Future<void> _confirmDelete() async {
    final provider = context.read<HistoryProvider>();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Xóa bản tóm tắt này?'),
        content: const Text('Nội dung sẽ bị xóa khỏi máy chủ và không thể khôi phục.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Giữ lại'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppConstants.errorColor),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Xóa'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    final ok = await provider.deleteItem(widget.summaryId);
    if (!mounted) return;

    if (!ok) {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text(provider.errorMessage ?? 'Không xóa được bản tóm tắt.'),
            backgroundColor: AppConstants.errorColor,
          ),
        );
      return;
    }
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Chi tiết tóm tắt'),
        actions: [
          if (_detail != null)
            IconButton(
              tooltip: 'Xóa khỏi lịch sử',
              icon: const Icon(Icons.delete_outline_rounded, color: Colors.white),
              onPressed: _confirmDelete,
            ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(color: AppConstants.primaryColor),
            SizedBox(height: 12),
            Text('Đang mở bản tóm tắt...'),
          ],
        ),
      );
    }

    final detail = _detail;
    if (detail == null) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.search_off_rounded, size: 56, color: Colors.grey.shade500),
            const SizedBox(height: 14),
            Text(
              _errorMessage ?? 'Không mở được bản tóm tắt này.',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 14.5, height: 1.5),
            ),
            const SizedBox(height: 20),
            OutlinedButton.icon(
              onPressed: () => Navigator.pop(context),
              icon: const Icon(Icons.arrow_back_rounded, size: 20),
              label: const Text('Quay lại'),
            ),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            detail.title.isEmpty ? 'Bản tóm tắt' : detail.title,
            style: const TextStyle(
              fontSize: 19,
              fontWeight: FontWeight.bold,
              color: AppConstants.primaryColor,
              height: 1.35,
            ),
          ),
          if (detail.description.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(
              detail.description,
              style: TextStyle(fontSize: 13.5, fontStyle: FontStyle.italic, color: Colors.grey.shade700),
            ),
          ],
          const SizedBox(height: 10),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              _MetaChip(label: detail.language.toUpperCase()),
              _MetaChip(label: detail.source),
              _MetaChip(label: '${detail.originalLength} ký tự gốc'),
              Text(
                _dateFormat.format(detail.createdAt),
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _SummaryCard(summary: detail.summary),
          const SizedBox(height: 16),
          _OriginalTextCard(
            text: detail.originalText,
            expanded: _showOriginal,
            onToggle: () => setState(() => _showOriginal = !_showOriginal),
          ),
          const SizedBox(height: 16),
          _QuizCard(
            quizzes: _quizzes,
            isLoading: _isLoadingQuizzes,
            isBusy: _isQuizBusy,
            canCreate: detail.originalLength >= AppConstants.minChars,
            dateFormat: _dateFormat,
            onCreate: _createQuiz,
            onOpen: _openExisting,
          ),
        ],
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.summary});

  final String summary;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AppConstants.primaryColor, width: 1),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Expanded(
                  child: Text(
                    'Bản tóm tắt',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                ),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      tooltip: 'Sao chép kết quả',
                      icon: const Icon(Icons.copy_rounded, size: 20, color: AppConstants.primaryColor),
                      onPressed: () {
                        Clipboard.setData(ClipboardData(text: summary));
                        ScaffoldMessenger.of(context)
                          ..hideCurrentSnackBar()
                          ..showSnackBar(
                            const SnackBar(
                              content: Text('Đã sao chép bản tóm tắt vào bộ nhớ tạm.'),
                              duration: Duration(seconds: 2),
                            ),
                          );
                      },
                    ),
                    IconButton(
                      tooltip: 'Chia sẻ kết quả',
                      icon: const Icon(Icons.share_rounded, size: 20, color: AppConstants.primaryColor),
                      onPressed: () => Share.share(summary),
                    ),
                  ],
                ),
              ],
            ),
            const Divider(),
            SelectableText(
              summary,
              style: const TextStyle(fontSize: 14, height: 1.6),
            ),
          ],
        ),
      ),
    );
  }
}

class _OriginalTextCard extends StatelessWidget {
  const _OriginalTextCard({
    required this.text,
    required this.expanded,
    required this.onToggle,
  });

  final String text;
  final bool expanded;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Văn bản gốc',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: AppConstants.textSecondaryColor,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              text,
              maxLines: expanded ? null : 8,
              overflow: expanded ? null : TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 13.5, height: 1.55),
            ),
            if (text.length > 600 || text.split('\n').length > 8) ...[
              const SizedBox(height: 4),
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  style: TextButton.styleFrom(
                    foregroundColor: AppConstants.secondaryColor,
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  ),
                  onPressed: onToggle,
                  icon: Icon(
                    expanded ? Icons.keyboard_arrow_up_rounded : Icons.keyboard_arrow_down_rounded,
                    size: 18,
                  ),
                  label: Text(
                    expanded ? 'Thu gọn ˄' : 'Xem thêm ˅',
                    style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _QuizCard extends StatelessWidget {
  const _QuizCard({
    required this.quizzes,
    required this.isLoading,
    required this.isBusy,
    required this.canCreate,
    required this.dateFormat,
    required this.onCreate,
    required this.onOpen,
  });

  final List<QuizListItem> quizzes;
  final bool isLoading;
  final bool isBusy;

  /// False khi văn bản gốc dưới ngưỡng 400 ký tự: server sẽ trả `QUIZ_TEXT_TOO_SHORT`,
  /// nên tốt hơn là không mời người dùng bấm.
  final bool canCreate;
  final DateFormat dateFormat;
  final Future<void> Function() onCreate;
  final Future<void> Function(QuizListItem) onOpen;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const Icon(Icons.quiz_outlined, size: 18, color: AppConstants.primaryColor),
                const SizedBox(width: 6),
                const Expanded(
                  child: Text(
                    'Trắc nghiệm',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                  ),
                ),
                if (quizzes.isNotEmpty)
                  Text(
                    '${quizzes.length} quiz',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            if (isLoading)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Center(
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2.4, color: AppConstants.secondaryColor),
                  ),
                ),
              )
            else if (quizzes.isEmpty)
              Text(
                'Chưa có bộ câu hỏi nào cho bản tóm tắt này.',
                style: TextStyle(fontSize: 13, color: Colors.grey.shade700),
              )
            else
              for (final quiz in quizzes)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  dense: true,
                  enabled: !isBusy,
                  title: Text(
                    '${quiz.questionCount} câu hỏi',
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600),
                  ),
                  subtitle: Text(
                    dateFormat.format(quiz.createdAt),
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                  ),
                  trailing: const Icon(Icons.chevron_right_rounded, color: AppConstants.secondaryColor),
                  onTap: () => onOpen(quiz),
                ),
            const SizedBox(height: 6),
            if (!canCreate)
              Text(
                'Văn bản gốc cần tối thiểu ${AppConstants.minChars} ký tự để tạo quiz.',
                style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600),
              )
            else
              FilledButton.icon(
                style: FilledButton.styleFrom(
                  backgroundColor: AppConstants.secondaryColor,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                onPressed: isBusy ? null : onCreate,
                icon: isBusy
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2.2, color: Colors.white),
                      )
                    : const Icon(Icons.auto_awesome_rounded, size: 18),
                label: Text(isBusy ? 'Đang tạo quiz, khoảng 30 giây...' : 'Tạo quiz mới'),
              ),
          ],
        ),
      ),
    );
  }
}

class _MetaChip extends StatelessWidget {
  const _MetaChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: AppConstants.secondaryColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 11.5,
          fontWeight: FontWeight.w600,
          color: AppConstants.secondaryColor,
        ),
      ),
    );
  }
}
