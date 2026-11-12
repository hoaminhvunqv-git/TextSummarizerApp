import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import 'package:share_plus/share_plus.dart';
import 'package:image_picker/image_picker.dart';
import '../core/constants.dart';
import '../providers/summary_provider.dart';
import 'history_view.dart';

class HomeView extends StatefulWidget {
  const HomeView({super.key});

  @override
  State<HomeView> createState() => _HomeViewState();
}

class _HomeViewState extends State<HomeView> {
  late final FocusNode _textFocusNode;
  bool _isExpanded = false;

  @override
  void initState() {
    super.initState();
    _textFocusNode = FocusNode();
    // Số lượt hôm nay phải lấy từ server: app bị tắt giữa ngày thì không được đoán còn 20.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) context.read<SummaryProvider>().loadUsage();
    });
  }

  @override
  void dispose() {
    _textFocusNode.dispose();
    super.dispose();
  }

  /// Kiểm tra xem văn bản có vượt quá 8 dòng hay không
  bool _checkExceeds8Lines(String text, double maxWidth) {
    if (text.isEmpty) return false;
    final span = TextSpan(
      text: text,
      style: const TextStyle(fontSize: 14, height: 1.5, fontFamily: 'Roboto'),
    );
    final tp = TextPainter(
      text: span,
      maxLines: 8,
      textDirection: TextDirection.ltr,
    );
    tp.layout(maxWidth: maxWidth);
    return tp.didExceedMaxLines;
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<SummaryProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('TextSummarizer AI'),
        actions: [
          IconButton(
            tooltip: 'Lịch sử tóm tắt',
            icon: const Icon(Icons.history_rounded),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const HistoryView()),
              );
            },
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 1. DÒNG THÔNG BÁO MÔ TẢ HỖ TRỢ NGÔN NGỮ
              Padding(
                padding: const EdgeInsets.only(left: 4.0, bottom: 8.0),
                child: Row(
                  children: [
                    Icon(Icons.language_rounded, size: 16, color: Colors.grey.shade600),
                    const SizedBox(width: 6),
                    Text(
                      'Hỗ trợ tóm tắt văn bản Tiếng Việt & Tiếng Anh',
                      style: TextStyle(
                        fontSize: 12.5,
                        fontStyle: FontStyle.italic,
                        color: Colors.grey.shade600,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),

              // 2. THANH CÔNG CỤ THAO TÁC NHANH (3 NÚT CHỨC NĂNG)
              _buildActionRibbon(context, provider),

              const SizedBox(height: 12),

              // 3. KHUNG SOẠN THẢO VĂN BẢN TRUNG TÂM (KÈM TÍNH NĂNG XEM THÊM / THU GỌN)
              _buildEditorCard(context, provider),

              const SizedBox(height: 20),

              // 4. BỘ CHỌN ĐỘ DÀI TÓM TẮT (Ngắn / Vừa / Dài)
              _buildLengthSelector(context, provider),

              const SizedBox(height: 24),

              // 5. NÚT HÀNH ĐỘNG CHÍNH (VÔ HIỆU HÓA KHI ĐANG XỬ LÝ HOẶC CHƯA ĐỦ ĐIỀU KIỆN)
              _buildSubmitButton(context, provider),

              // 5b. LƯỢT CÒN LẠI HÔM NAY CỦA THIẾT BỊ
              _buildUsageLine(context, provider),

              // 6. HIỂN THỊ KẾT QUẢ TÓM TẮT (NẾU CÓ)
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

  /// 3 nút chức năng phía trên khung soạn thảo
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
                onPressed: provider.isLoading
                    ? null
                    : () async {
                        // Dán trực tiếp văn bản từ clipboard vào ô soạn thảo
                        final bool pasted = await provider.pasteFromClipboard();
                        if (context.mounted && !pasted) {
                          ScaffoldMessenger.of(context).hideCurrentSnackBar();
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Bộ nhớ tạm chưa có nội dung văn bản'),
                              duration: Duration(seconds: 2),
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        }
                      },
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
                        _showImageSourceSheet(context, provider);
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
                    : () async {
                        await provider.extractFile();
                        if (context.mounted && provider.errorMessage != null) {
                          ScaffoldMessenger.of(context).hideCurrentSnackBar();
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(provider.errorMessage!),
                              backgroundColor: AppConstants.errorColor,
                              duration: const Duration(seconds: 3),
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        }
                      },
              ),
            ),
            if (provider.textController.text.isNotEmpty) ...[
              const SizedBox(width: 6),
              Expanded(
                child: _buildRibbonButton(
                  icon: Icons.delete_sweep_rounded,
                  label: 'Xóa tất cả',
                  color: Colors.red.shade400,
                  onPressed: provider.isLoading
                      ? null
                      : () {
                          provider.clearText();
                          setState(() {
                            _isExpanded = false;
                          });
                        },
                ),
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

  /// Khung soạn thảo văn bản kèm tính năng Xem thêm / Thu gọn và Gradient Mask
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
        child: LayoutBuilder(
          builder: (context, constraints) {
            // Chiều rộng khả dụng của khung text (trừ padding)
            final double textWidth = constraints.maxWidth;
            final bool exceeds8Lines = _checkExceeds8Lines(provider.textController.text, textWidth);

            Widget textFieldWidget = TextField(
              controller: provider.textController,
              focusNode: _textFocusNode,
              enabled: !provider.isLoading,
              maxLines: null,
              minLines: 8,
              keyboardType: TextInputType.multiline,
              style: const TextStyle(fontSize: 14, height: 1.5, fontFamily: 'Roboto'),
              decoration: const InputDecoration(
                border: InputBorder.none,
                enabledBorder: InputBorder.none,
                focusedBorder: InputBorder.none,
                contentPadding: EdgeInsets.zero,
                hintText: 'Nhập, dán hoặc quét văn bản cần tóm tắt tại đây...\n(Nhận tóm tắt từ 400 đến 30.000 ký tự)',
              ),
            );

            // Khi văn bản vượt quá 8 dòng và đang ở trạng thái thu gọn:
            // Giới hạn chiều cao tương đương 8 dòng và phủ hiệu ứng Gradient Fade mờ dần ở đáy
            if (exceeds8Lines && !_isExpanded) {
              const double maxCollapsedHeight = 8 * 14 * 1.5; // ~168px
              textFieldWidget = SizedBox(
                height: maxCollapsedHeight,
                child: ShaderMask(
                  shaderCallback: (Rect bounds) {
                    return const LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.black,
                        Colors.black,
                        Colors.transparent,
                      ],
                      stops: [0.0, 0.70, 1.0], // Mờ dần ở khoảng 2 dòng cuối
                    ).createShader(bounds);
                  },
                  blendMode: BlendMode.dstIn,
                  child: SingleChildScrollView(
                    physics: const NeverScrollableScrollPhysics(),
                    child: textFieldWidget,
                  ),
                ),
              );
            }

            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                textFieldWidget,

                // Nút điều khiển "Xem thêm ˅ / Thu gọn ˄" khi văn bản dài hơn 8 dòng
                if (exceeds8Lines) ...[
                  const SizedBox(height: 4),
                  Center(
                    child: TextButton.icon(
                      style: TextButton.styleFrom(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                        minimumSize: Size.zero,
                        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        foregroundColor: AppConstants.secondaryColor,
                      ),
                      onPressed: () {
                        setState(() {
                          _isExpanded = !_isExpanded;
                        });
                      },
                      icon: Icon(
                        _isExpanded ? Icons.keyboard_arrow_up_rounded : Icons.keyboard_arrow_down_rounded,
                        size: 18,
                      ),
                      label: Text(
                        _isExpanded ? 'Thu gọn ˄' : 'Xem thêm ˅',
                        style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
                ],

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
            );
          },
        ),
      ),
    );
  }

  /// Bộ chọn độ dài tóm tắt: Ngắn / Vừa / Dài
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
              subtitle: '~12% bản gốc',
            ),
            const SizedBox(width: 8),
            _buildLengthChip(
              context: context,
              provider: provider,
              lengthKey: 'medium',
              title: 'Vừa',
              subtitle: '~22% bản gốc',
            ),
            const SizedBox(width: 8),
            _buildLengthChip(
              context: context,
              provider: provider,
              lengthKey: 'long',
              title: 'Dài', // Đã đổi nhãn từ 'Chi tiết' thành 'Dài'
              subtitle: '~35% bản gốc',
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
    final bool isUnlocked = provider.isLengthUnlocked(lengthKey);
    final bool isSelected = isUnlocked && provider.selectedLength == lengthKey;
    final String detailText = isUnlocked
        ? subtitle
        : 'Cần thêm ~${provider.missingCharsFor(lengthKey)} ký tự';

    return Expanded(
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: isUnlocked && !provider.isLoading ? () => provider.setSelectedLength(lengthKey) : null,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
          decoration: BoxDecoration(
            color: isSelected
                ? AppConstants.primaryColor
                : (isUnlocked ? Colors.white : Colors.grey.shade100),
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
                  color: isSelected
                      ? Colors.white
                      : (isUnlocked ? AppConstants.textPrimaryColor : Colors.grey.shade500),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                detailText,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 11,
                  color: isSelected
                      ? Colors.white70
                      : (isUnlocked ? AppConstants.textSecondaryColor : Colors.grey.shade500),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Nút Tóm tắt chính (Vô hiệu hóa khi đang xử lý hoặc chưa đủ 400 ký tự)
  Widget _buildSubmitButton(BuildContext context, SummaryProvider provider) {
    final bool canSubmit = provider.canSubmit && !provider.isLoading;

    return SizedBox(
      height: 50,
      child: ElevatedButton(
        onPressed: canSubmit
            ? () async {
                FocusScope.of(context).unfocus();
                await provider.summarize();
                if (context.mounted) {
                  if (provider.errorMessage != null) {
                    // Hiển thị SnackBar lỗi
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text(provider.errorMessage!),
                        backgroundColor: AppConstants.errorColor,
                      ),
                    );
                  } else if (provider.summaryResult != null) {
                    // Hiển thị SnackBar thành công với độ dài
                    final lengthLabels = {
                      'short': 'Ngắn',
                      'medium': 'Vừa',
                      'long': 'Dài',
                    };
                    final lengthLabel = lengthLabels[provider.selectedLength] ?? 'Vừa';
                    
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text('Đã tóm tắt văn bản của bạn ($lengthLabel)'),
                        backgroundColor: AppConstants.successColor,
                        duration: const Duration(seconds: 2),
                      ),
                    );
                  }
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

  /// Số lượt còn lại hôm nay của thiết bị, đọc từ GET /usage và cập nhật theo phản hồi
  /// của mỗi lần tóm tắt. Có ba trạng thái hiển thị: đang đọc / chưa đọc được / còn N.
  /// Không bao giờ ẩn im lặng: người dùng cần biết là app chưa lấy được con số, vì
  /// một dòng trống trông hệt như "còn rất nhiều lượt".
  Widget _buildUsageLine(BuildContext context, SummaryProvider provider) {
    final int? remaining = provider.summaryRemaining;
    final String label;
    final Color color;
    final IconData icon;

    if (provider.isReadingUsage) {
      label = 'Đang kiểm tra lượt còn lại hôm nay...';
      color = AppConstants.textSecondaryColor;
      icon = Icons.schedule_rounded;
    } else if (remaining == null) {
      label = 'Chưa đọc được lượt còn lại hôm nay.';
      color = AppConstants.textSecondaryColor;
      icon = Icons.info_outline_rounded;
    } else if (remaining <= 0) {
      label = 'Hôm nay bạn đã dùng hết lượt tóm tắt. Lượt mới bắt đầu sau nửa đêm.';
      color = AppConstants.errorColor;
      icon = Icons.schedule_rounded;
    } else {
      label = 'Hôm nay còn $remaining lượt tóm tắt';
      color = AppConstants.textSecondaryColor;
      icon = Icons.schedule_rounded;
    }

    return Padding(
      padding: const EdgeInsets.only(top: 10, bottom: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 15, color: color),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              label,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ),
        ],
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
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
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
                    IconButton(
                      tooltip: 'Chia sẻ kết quả',
                      icon: const Icon(Icons.share_rounded, size: 20, color: AppConstants.primaryColor),
                      onPressed: () {
                        Share.share(summary);
                      },
                    ),
                  ],
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

  /// Hiển thị bottom sheet chọn nguồn ảnh (Camera hoặc Gallery) cho OCR
  void _showImageSourceSheet(BuildContext context, SummaryProvider provider) {
    showModalBottomSheet(
      context: context,
      builder: (BuildContext sheetContext) {
        void pick(ImageSource source) {
          Navigator.pop(sheetContext);
          // Không await trong builder: `context` của sheet đã bị pop, chỉ còn
          // `context` của màn hình chính mới dùng để hiện SnackBar được.
          _runOcr(context, provider, source);
        }

        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.camera_alt_outlined),
                title: const Text('Chụp ảnh'),
                onTap: () => pick(ImageSource.camera),
              ),
              ListTile(
                leading: const Icon(Icons.photo_library_outlined),
                title: const Text('Chọn từ thư viện'),
                onTap: () => pick(ImageSource.gallery),
              ),
            ],
          ),
        );
      },
    );
  }

  /// OCR chạy ~7s và lỗi của nó (_errorMessage) không tự hiện lên đâu ở màn này,
  /// nên phải chờ xong rồi nói thẳng bằng SnackBar — bao gồm cả "hết lượt" của server.
  Future<void> _runOcr(
    BuildContext context,
    SummaryProvider provider,
    ImageSource source,
  ) async {
    await provider.recognizeText(source);
    if (!context.mounted) return;
    final String? message = provider.errorMessage;
    if (message == null) return;

    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: AppConstants.errorColor,
        ),
      );
  }
}
