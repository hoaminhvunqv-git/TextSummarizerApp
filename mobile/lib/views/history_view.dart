import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../core/constants.dart';
import '../models/history_models.dart';
import '../providers/history_provider.dart';
import 'summary_detail_view.dart';

/// Danh sách bản tóm tắt đã lưu trên máy chủ, kèm kéo để làm mới và xóa từng bản ghi.
class HistoryView extends StatefulWidget {
  const HistoryView({super.key});

  @override
  State<HistoryView> createState() => _HistoryViewState();
}

class _HistoryViewState extends State<HistoryView> {
  static final DateFormat _dateFormat = DateFormat('dd/MM/yyyy HH:mm');
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<HistoryProvider>().refresh();
    });
  }

  @override
  void dispose() {
    _scrollController
      ..removeListener(_onScroll)
      ..dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final position = _scrollController.position;
    if (position.pixels >= position.maxScrollExtent - 240) {
      context.read<HistoryProvider>().loadMore();
    }
  }

  Future<void> _confirmDelete(HistoryItem item) async {
    final provider = context.read<HistoryProvider>();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Xóa bản tóm tắt này?'),
        content: Text(
          '"${item.title}" sẽ bị xóa khỏi máy chủ và không thể khôi phục.',
          maxLines: 3,
          overflow: TextOverflow.ellipsis,
        ),
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

    final ok = await provider.deleteItem(item.id);
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(ok ? 'Đã xóa khỏi lịch sử.' : provider.errorMessage ?? 'Không xóa được bản tóm tắt.'),
          backgroundColor: ok ? AppConstants.successColor : AppConstants.errorColor,
        ),
      );
  }

  Future<void> _openDetail(HistoryItem item) async {
    // Màn chi tiết dùng lại chính HistoryProvider, nên nếu xóa ở đó thì danh sách
    // đã tự cập nhật trước khi quay về — không cần đồng bộ thêm.
    await Navigator.push<void>(
      context,
      MaterialPageRoute(builder: (_) => SummaryDetailView(summaryId: item.id)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<HistoryProvider>();

    return Scaffold(
      appBar: AppBar(title: const Text('Lịch sử tóm tắt')),
      body: _buildBody(provider),
    );
  }

  Widget _buildBody(HistoryProvider provider) {
    if (provider.isPristine && provider.isLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(color: AppConstants.primaryColor),
            SizedBox(height: 12),
            Text('Đang tải lịch sử...'),
          ],
        ),
      );
    }

    if (provider.items.isEmpty) {
      if (provider.errorMessage != null) {
        return _ErrorState(message: provider.errorMessage!, onRetry: provider.refresh);
      }
      return _EmptyState(onCreate: () => Navigator.pop(context));
    }

    return RefreshIndicator(
      onRefresh: () => provider.refresh(),
      color: AppConstants.primaryColor,
      child: ListView.separated(
        controller: _scrollController,
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        itemCount: provider.items.length + 1,
        separatorBuilder: (_, _) => const SizedBox(height: 10),
        itemBuilder: (context, index) {
          if (index == provider.items.length) return _buildFooter(provider);
          final item = provider.items[index];
          return _HistoryTile(
            item: item,
            formattedDate: _dateFormat.format(item.createdAt),
            onTap: () => _openDetail(item),
            onDelete: () => _confirmDelete(item),
          );
        },
      ),
    );
  }

  Widget _buildFooter(HistoryProvider provider) {
    if (provider.isLoading) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 16),
        child: Center(
          child: SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2.5, color: AppConstants.secondaryColor),
          ),
        ),
      );
    }
    if (provider.hasMore) return const SizedBox(height: 8);
    // `hasMore` tắt được cả khi trang kế trả về rỗng, nên "toàn bộ" chỉ nói được
    // khi số dòng trên màn hình thực sự bằng số server báo.
    final int shown = provider.items.length;
    final int total = provider.total;
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Center(
        child: Text(
          shown >= total
              ? 'Đã hiển thị toàn bộ $shown bản tóm tắt'
              : 'Đã hiển thị $shown/$total bản tóm tắt',
          style: TextStyle(fontSize: 12.5, color: Colors.grey.shade600),
        ),
      ),
    );
  }
}

class _HistoryTile extends StatelessWidget {
  const _HistoryTile({
    required this.item,
    required this.formattedDate,
    required this.onTap,
    required this.onDelete,
  });

  final HistoryItem item;
  final String formattedDate;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 12, 6, 12),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.title.isEmpty ? 'Bản tóm tắt' : item.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.bold,
                        color: AppConstants.primaryColor,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      item.description,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 13, color: Colors.grey.shade700, height: 1.4),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(Icons.schedule, size: 13, color: Colors.grey.shade600),
                        const SizedBox(width: 4),
                        Text(
                          formattedDate,
                          style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                        ),
                        const SizedBox(width: 10),
                        _MetaChip(label: item.language.toUpperCase()),
                        const SizedBox(width: 6),
                        _MetaChip(label: item.source),
                      ],
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'Xóa khỏi lịch sử',
                icon: Icon(Icons.delete_outline_rounded, size: 22, color: Colors.red.shade400),
                onPressed: onDelete,
              ),
            ],
          ),
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
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
      decoration: BoxDecoration(
        color: AppConstants.secondaryColor.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: AppConstants.secondaryColor,
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.onCreate});

  final VoidCallback onCreate;

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 60),
        Icon(Icons.history_rounded, size: 64, color: Colors.grey.shade400),
        const SizedBox(height: 16),
        const Text(
          'Chưa có bản tóm tắt nào',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        Text(
          'Mỗi lần tóm tắt xong, nội dung sẽ được lưu lại ở đây để bạn đọc lại bất cứ lúc nào.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 13.5, color: Colors.grey.shade700, height: 1.5),
        ),
        const SizedBox(height: 20),
        Center(
          child: ElevatedButton.icon(
            onPressed: onCreate,
            icon: const Icon(Icons.auto_awesome_rounded, size: 20),
            label: const Text('Tạo bản tóm tắt đầu tiên'),
          ),
        ),
      ],
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(24),
      children: [
        const SizedBox(height: 60),
        Icon(Icons.cloud_off_rounded, size: 60, color: AppConstants.errorColor),
        const SizedBox(height: 16),
        Text(
          message,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 14.5, height: 1.5),
        ),
        const SizedBox(height: 20),
        Center(
          child: OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh_rounded, size: 20),
            label: const Text('Tải lại'),
          ),
        ),
      ],
    );
  }
}
