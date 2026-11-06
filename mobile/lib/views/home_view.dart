import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../core/constants.dart';
import '../providers/summary_provider.dart';

class HomeView extends StatelessWidget {
  const HomeView({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SummaryProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('TextSummarizer AI'),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. THANH CÔNG CỤ THAO TÁC NHANH (3 NÚT CHỨC NĂNG)
              _buildActionRibbon(context, provider),

              const SizedBox(height: 12),

              // 2. KHUNG SOẠN THẢO VĂN BẢN TRUNG TÂM
              _buildEditorCard(context, provider),

              const SizedBox(height: 20),

              // 3. BỘ CHỌN ĐỘ DÀI TÓM TẮT
              _buildLengthSelector(context, provider),

              const SizedBox(height: 24),

              // 4. NÚT HÀNH ĐỘNG CHÍNH (VÔ HIỆU HÓA KHI ĐANG XỬ LÝ HOẶC CHƯA ĐỦ ĐIỀU KIỆN)
              _buildSubmitButton(context, provider),

              // 5. HIỂN THỊ KẾT QUẢ TÓM TẮT (NẾU CÓ)
              if (provider.summaryResult != null) ...[
                const SizedBox(height: 24),
                _buildResultCard(context, provider),
              ],
            ],
          ),
        ),
      ),
    );
  }

  /// 3 nút chức năng phân bố chuyên nghiệp phía trên khung soạn thảo
  Widget _buildActionRibbon(BuildContext context, SummaryProvider provider) {
    return Card(
      elevation: 0.5,
      color: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        child: Row(
          children: [
            Expanded(
              child: _buildRibbonButton(
                icon: Icons.paste_rounded,
                label: 'Dán chữ',
                color: AppConstants.primaryColor,
                onPressed: provider.isLoading ? null : () => provider.pasteFromClipboard(),
              ),
            ),
            const SizedBox(width: 6),
            Expanded(
              child: _buildRibbonButton(
                icon: Icons.camera_alt_outlined,
                label: 'Quét ảnh',
                color: AppConstants.secondaryColor,
                onPressed: provider.isLoading
                    ? null
                    : () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Tính năng Quét ảnh OCR đang được kết nối.'),
                            duration: Duration(seconds: 2),
                          ),
                        );
                      },
              ),
            ),
            const SizedBox(width: 6),
            Expanded(
              child: _buildRibbonButton(
                icon: Icons.upload_file_outlined,
                label: 'Chọn tệp',
                color: AppConstants.secondaryColor,
                onPressed: provider.isLoading
                    ? null
                    : () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Tính năng Trích xuất file đang được kết nối.'),
                            duration: Duration(seconds: 2),
                          ),
                        );
                      },
              ),
            ),
            if (provider.textController.text.isNotEmpty) ...[
              const SizedBox(width: 4),
              IconButton(
                tooltip: 'Xóa nội dung',
                icon: const Icon(Icons.clear_rounded, color: Colors.grey, size: 20),
                onPressed: provider.isLoading ? null : () => provider.clearText(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildRibbonButton({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback? onPressed,
  }) {
    return TextButton.icon(
      style: TextButton.styleFrom(
        foregroundColor: color,
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        backgroundColor: color.withValues(alpha: 0.06),
      ),
      icon: Icon(icon, size: 18),
      label: Text(
        label,
        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
      ),
      onPressed: onPressed,
    );
  }

  /// Khung nhập văn bản chính kèm bộ đếm ký tự
  Widget _buildEditorCard(BuildContext context, SummaryProvider provider) {
    final charCount = provider.charCount;
    Color counterColor = AppConstants.textSecondaryColor;
    String statusNote = '';

    if (charCount > 0 && charCount < AppConstants.minChars) {
      counterColor = AppConstants.errorColor;
      statusNote = '(Cần thêm ${AppConstants.minChars - charCount} ký tự)';
    } else if (charCount > AppConstants.maxChars) {
      counterColor = AppConstants.errorColor;
      statusNote = '(Vượt quá ${charCount - AppConstants.maxChars} ký tự)';
    } else if (charCount >= AppConstants.minChars) {
      counterColor = AppConstants.successColor;
      statusNote = '(Hợp lệ)';
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14.0),
        child: Column(
          children: [
            TextField(
              controller: provider.textController,
              enabled: !provider.isLoading,
              maxLines: null,
              minLines: 8,
              keyboardType: TextInputType.multiline,
              style: const TextStyle(fontSize: 14, height: 1.5),
              decoration: const InputDecoration(
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
                focusedBorder: InputBorder.none,
                contentPadding: EdgeInsets.zero,
                hintText: 'Nhập, dán hoặc quét văn bản cần tóm tắt tại đây...\n(Tối thiểu 200 đến 30.000 ký tự)',
              ),
            ),
            const Divider(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  statusNote,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    color: counterColor,
                  ),
                ),
                Text(
                  '$charCount / ${AppConstants.maxChars} ký tự',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: counterColor,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  /// Bộ chọn độ dài tóm tắt: Ngắn / Vừa / Chi tiết
  Widget _buildLengthSelector(BuildContext context, SummaryProvider provider) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Độ dài tóm tắt mong muốn:',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: AppConstants.textPrimaryColor,
          ),
        ),
        const SizedBox(height: 10),
        Row(
          children: [
            _buildLengthChip(
              context: context,
              provider: provider,
              lengthKey: 'short',
              title: 'Ngắn',
              subtitle: '≤ 100 từ',
            ),
            const SizedBox(width: 8),
            _buildLengthChip(
              context: context,
              provider: provider,
              lengthKey: 'medium',
              title: 'Vừa',
              subtitle: '≤ 200 từ',
            ),
            const SizedBox(width: 8),
            _buildLengthChip(
              context: context,
              provider: provider,
              lengthKey: 'long',
              title: 'Chi tiết',
              subtitle: '≤ 350 từ',
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildLengthChip({
    required BuildContext context,
    required SummaryProvider provider,
    required String lengthKey,
    required String title,
    required String subtitle,
  }) {
    final isSelected = provider.selectedLength == lengthKey;

    return Expanded(
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: provider.isLoading ? null : () => provider.setSelectedLength(lengthKey),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppConstants.primaryColor : Colors.white,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: isSelected ? AppConstants.primaryColor : Colors.grey.shade300,
              width: isSelected ? 1.5 : 1.0,
            ),
          ),
          child: Column(
            children: [
              Text(
                title,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: isSelected ? Colors.white : AppConstants.textPrimaryColor,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: TextStyle(
                  fontSize: 11,
                  color: isSelected ? Colors.white70 : AppConstants.textSecondaryColor,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Nút Tóm tắt chính (Vô hiệu hóa khi đang xử lý hoặc chưa đủ 200 ký tự)
  Widget _buildSubmitButton(BuildContext context, SummaryProvider provider) {
    final bool canSubmit = provider.isValidLength && !provider.isLoading;

    return SizedBox(
      height: 50,
      child: ElevatedButton(
        onPressed: canSubmit
            ? () async {
                FocusScope.of(context).unfocus();
                await provider.summarize();
                if (context.mounted && provider.errorMessage != null) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(provider.errorMessage!),
                      backgroundColor: AppConstants.errorColor,
                    ),
                  );
                }
              }
            : null,
        child: provider.isLoading
            ? const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SpinKitThreeBounce(
                    color: Colors.white,
                    size: 20.0,
                  ),
                  SizedBox(width: 12),
                  Text(
                    'Đang phân tích văn bản...',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                  ),
                ],
              )
            : const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.auto_awesome_rounded, size: 20),
                  SizedBox(width: 8),
                  Text(
                    'Tóm tắt văn bản',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
      ),
    );
  }

  /// Khung hiển thị kết quả tóm tắt khi hoàn thành
  Widget _buildResultCard(BuildContext context, SummaryProvider provider) {
    final result = provider.summaryResult!;
    final title = result['title'] ?? 'Bản tóm tắt';
    final summary = result['summary'] ?? '';

    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AppConstants.primaryColor, width: 1),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    title,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.bold,
                      color: AppConstants.primaryColor,
                    ),
                  ),
                ),
                IconButton(
                  tooltip: 'Sao chép kết quả',
                  icon: const Icon(Icons.copy_rounded, size: 20, color: AppConstants.primaryColor),
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: summary));
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Đã sao chép bản tóm tắt vào bộ nhớ tạm.'),
                        duration: Duration(seconds: 2),
                      ),
                    );
                  },
                ),
              ],
            ),
            const Divider(),
            const SizedBox(height: 8),
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
