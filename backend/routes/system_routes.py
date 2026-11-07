from flask import Blueprint, jsonify

try:
    from backend.config import Config
    from backend.extensions import limiter
    from backend.utils.responses import success_response
except ImportError:
    from config import Config
    from extensions import limiter
    from utils.responses import success_response

system_bp = Blueprint("system", __name__)


@system_bp.route("/health", methods=["GET"])
@limiter.exempt
def health():
    """Kiểm tra máy chủ còn sống (không prefix /api/v1, không auth, không đụng DB)."""
    return jsonify({"status": "ok"}), 200


@system_bp.route("/api/v1/config", methods=["GET"])
def get_config():
    """Trả về phiên bản tối thiểu và các hạn mức của hệ thống."""
    data = {
        "min_app_version": Config.MIN_APP_VERSION,
        "limits": {
          "min_chars": Config.MIN_CHARS,
          "max_chars": Config.MAX_CHARS,
          "max_file_mb": Config.MAX_FILE_MB,
          "daily_summary": Config.DAILY_SUMMARY_LIMIT,
          "daily_quiz": Config.DAILY_QUIZ_LIMIT,
        },
    }
    return success_response(data=data)
