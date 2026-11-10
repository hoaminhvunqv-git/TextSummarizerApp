import sys
from pathlib import Path

# Đảm bảo đường dẫn import hoạt động cả khi chạy từ backend/ hoặc thư mục gốc
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
for p in (str(BASE_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import logging
from flask import Flask, request
from flask_cors import CORS
from flask_limiter.errors import RateLimitExceeded
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

try:
    from backend.config import Config
    from backend.extensions import limiter
    from backend.utils.errors import AppError, ERROR_DEFINITIONS, ErrorCode
    from backend.utils.responses import error_response
    from backend.routes.system_routes import system_bp
    from backend.routes.summary_routes import summary_bp
    from backend.routes.file_routes import file_bp
    from backend.routes.ocr_routes import ocr_bp
except ImportError:
    from config import Config
    from extensions import limiter
    from utils.errors import AppError, ERROR_DEFINITIONS, ErrorCode
    from utils.responses import error_response
    from routes.system_routes import system_bp
    from routes.summary_routes import summary_bp
    from routes.file_routes import file_bp
    from routes.ocr_routes import ocr_bp

# Cấu hình logging cơ bản (không log nội dung người dùng theo CLAUDE.md)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("text_summarizer")


def _limit_granularity(err) -> str:
    """Trả về 'day'/'minute'/... của giới hạn Flask-Limiter vừa chạm trần, hoặc '' nếu không phải."""
    if not isinstance(err, RateLimitExceeded):
        return ""
    # Đường đi này thuộc internals của flask_limiter/limits, không có API công khai.
    rate_item = getattr(getattr(err, "limit", None), "limit", None)
    return getattr(getattr(rate_item, "GRANULARITY", None), "name", "") or ""


def create_app(config_class=Config) -> Flask:
    """Application factory khởi tạo ứng dụng Flask."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Hiển thị ký tự tiếng Việt UTF-8 trực tiếp thay vì mã hoá unicode escape (\u...)
    app.json.ensure_ascii = False

    # Bật CORS cho môi trường dev/web test (mobile app giao tiếp qua HTTPS không cần CORS)
    CORS(app)

    # Render đặt Flask sau reverse proxy: không có ProxyFix thì request.remote_addr
    # luôn là IP của proxy và mọi người dùng bị tính chung một giới hạn.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Giới hạn spam: mặc định 30/phút và 20/ngày, chốt theo X-Device-ID (xem extensions.py)
    limiter.init_app(app)

    # Đăng ký Blueprints
    app.register_blueprint(system_bp)
    app.register_blueprint(summary_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(ocr_bp)

    # Đăng ký Global Error Handlers
    @app.errorhandler(AppError)
    def handle_app_error(err: AppError):
        """Bắt các lỗi nghiệp vụ chủ động ném ra trong ứng dụng."""
        return error_response(
            error_code=err.error_code,
            message=err.message,
            status_code=err.status_code,
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        """Bắt và chuyển đổi các lỗi HTTP chuẩn sang format JSON của dự án."""
        logger.error(f"HTTPException {err.code} tại {request.method} {request.path}")
        status_code = err.code or 500
        if status_code == 404:
            return error_response(
                error_code=ErrorCode.NOT_FOUND,
                message="Không tìm thấy dữ liệu.",
                status_code=404,
            )
        if status_code == 413:
            return error_response(
                error_code=ErrorCode.FILE_TOO_LARGE,
                message="Dung lượng file vượt quá 10MB.",
                status_code=413,
            )
        if status_code == 429:
            # 429 do Flask-Limiter ném ra có hai loại: chặn spam theo phút và trần
            # 20 lượt/ngày theo thiết bị. Trần ngày phải báo hết lượt, không báo "thao tác nhanh quá".
            if _limit_granularity(err) == "day":
                return error_response(
                    error_code=ErrorCode.QUOTA_EXCEEDED,
                    message=ERROR_DEFINITIONS[ErrorCode.QUOTA_EXCEEDED][1],
                    status_code=429,
                )
            return error_response(
                error_code=ErrorCode.RATE_LIMITED,
                message="Bạn thao tác quá nhanh. Vui lòng thử lại sau ít phút.",
                status_code=429,
            )
        # Các mã HTTP khác
        return error_response(
            error_code=ErrorCode.VALIDATION_ERROR if status_code == 400 else ErrorCode.INTERNAL_ERROR,
            message=err.description or "Yêu cầu không hợp lệ.",
            status_code=status_code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_exception(err: Exception):
        """Bắt mọi ngoại lệ không lường trước: ghi log loại lỗi (không log dữ liệu nhạy cảm) và trả về 500."""
        logger.error(f"Lỗi không lường trước: {type(err).__name__}: {str(err)}")
        return error_response(
            error_code=ErrorCode.INTERNAL_ERROR,
            message="Đã có lỗi xảy ra. Vui lòng thử lại.",
            status_code=500,
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
