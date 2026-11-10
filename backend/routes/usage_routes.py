from flask import Blueprint, g

try:
    from backend.services import quota_service
    from backend.utils.responses import success_response
    from backend.utils.validators import require_device_and_version
except ImportError:
    from services import quota_service
    from utils.responses import success_response
    from utils.validators import require_device_and_version

usage_bp = Blueprint("usage", __name__)


@usage_bp.route("/api/v1/usage", methods=["GET"])
@require_device_and_version
def get_usage():
    """Lượt còn lại hôm nay của thiết bị (hoặc tài khoản khi đã có JWT ở GĐ4)."""
    owner = quota_service.owner_key(device_id=getattr(g, "device_id", None))
    return success_response(data=quota_service.get_usage(owner))
