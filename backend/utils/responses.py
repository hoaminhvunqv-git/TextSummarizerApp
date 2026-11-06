from typing import Any, Optional
from flask import jsonify, Response


def success_response(
    data: Optional[Any] = None,
    message: str = "Xử lý thành công",
    status_code: int = 200,
) -> tuple[Response, int]:
    """Tạo phản hồi JSON chuẩn khi thành công theo docs/API.md."""
    payload = {
        "success": True,
        "message": message,
        "data": {} if data is None else data,
    }
    return jsonify(payload), status_code


def error_response(
    error_code: str,
    message: str,
    status_code: int = 400,
) -> tuple[Response, int]:
    """Tạo phản hồi JSON chuẩn khi có lỗi theo docs/API.md."""
    payload = {
        "success": False,
        "error_code": error_code,
        "message": message,
    }
    return jsonify(payload), status_code
