from typing import Optional


class ErrorCode:
    TEXT_TOO_SHORT = "TEXT_TOO_SHORT"
    TEXT_TOO_LONG = "TEXT_TOO_LONG"
    QUIZ_TEXT_TOO_SHORT = "QUIZ_TEXT_TOO_SHORT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_UNSUPPORTED = "FILE_UNSUPPORTED"
    FILE_EMPTY = "FILE_EMPTY"
    PDF_SCANNED = "PDF_SCANNED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_DEVICE_ID = "INVALID_DEVICE_ID"
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    NOT_FOUND = "NOT_FOUND"
    EMAIL_EXISTS = "EMAIL_EXISTS"
    OTP_INVALID = "OTP_INVALID"
    OTP_EXPIRED = "OTP_EXPIRED"
    OTP_TOO_MANY_ATTEMPTS = "OTP_TOO_MANY_ATTEMPTS"
    OTP_RESEND_COOLDOWN = "OTP_RESEND_COOLDOWN"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    UPDATE_REQUIRED = "UPDATE_REQUIRED"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Bảng định nghĩa HTTP status code và thông điệp chuẩn theo docs/API.md
ERROR_DEFINITIONS = {
    ErrorCode.TEXT_TOO_SHORT: (400, "Văn bản quá ngắn để tóm tắt. Hãy nhập ít nhất 200 ký tự."),
    ErrorCode.TEXT_TOO_LONG: (400, "Văn bản vượt quá giới hạn 30.000 ký tự. Vui lòng chia nhỏ nội dung."),
    ErrorCode.QUIZ_TEXT_TOO_SHORT: (400, "Văn bản quá ngắn để tạo quiz (cần ít nhất 400 ký tự)."),
    ErrorCode.FILE_TOO_LARGE: (413, "Dung lượng file vượt quá 10MB."),
    ErrorCode.FILE_UNSUPPORTED: (400, "Chỉ hỗ trợ file .txt, .docx, .pdf."),
    ErrorCode.FILE_EMPTY: (400, "File không có nội dung văn bản."),
    ErrorCode.PDF_SCANNED: (400, "Không thể đọc văn bản từ file này. Hãy dùng tính năng Quét ảnh OCR."),
    ErrorCode.VALIDATION_ERROR: (400, "Dữ liệu gửi lên không hợp lệ."),
    ErrorCode.INVALID_DEVICE_ID: (400, "Thiết bị không hợp lệ. Hãy khởi động lại ứng dụng."),
    ErrorCode.UNAUTHORIZED: (401, "Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại."),
    ErrorCode.INVALID_CREDENTIALS: (401, "Email hoặc mật khẩu không đúng."),
    ErrorCode.EMAIL_NOT_VERIFIED: (403, "Email chưa được xác thực."),
    ErrorCode.NOT_FOUND: (404, "Không tìm thấy dữ liệu."),
    ErrorCode.EMAIL_EXISTS: (409, "Email đã được đăng ký."),
    ErrorCode.OTP_INVALID: (400, "Mã OTP không đúng."),
    ErrorCode.OTP_EXPIRED: (400, "Mã OTP đã hết hạn. Hãy yêu cầu mã mới."),
    ErrorCode.OTP_TOO_MANY_ATTEMPTS: (429, "Nhập sai quá nhiều lần. Hãy yêu cầu mã mới."),
    ErrorCode.OTP_RESEND_COOLDOWN: (429, "Vui lòng đợi 60 giây trước khi gửi lại mã."),
    ErrorCode.QUOTA_EXCEEDED: (429, "Bạn đã dùng hết quota trong ngày. Vui lòng quay lại vào ngày mai."),
    ErrorCode.RATE_LIMITED: (429, "Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút."),
    ErrorCode.UPDATE_REQUIRED: (426, "Vui lòng cập nhật ứng dụng lên phiên bản mới."),
    ErrorCode.AI_UNAVAILABLE: (503, "Tính năng tạo quiz tạm thời không khả dụng. Vui lòng thử lại sau."),
    ErrorCode.INTERNAL_ERROR: (500, "Đã có lỗi xảy ra. Vui lòng thử lại."),
}


class AppError(Exception):
    """Custom exception chuẩn hoá theo mã lỗi dự án."""

    def __init__(
        self,
        error_code: str,
        message: Optional[str] = None,
        status_code: Optional[int] = None,
    ):
        self.error_code = error_code
        default_status, default_message = ERROR_DEFINITIONS.get(
            error_code, (400, "Đã có lỗi xảy ra.")
        )
        self.message = message if message is not None else default_message
        self.status_code = status_code if status_code is not None else default_status
        super().__init__(self.message)
