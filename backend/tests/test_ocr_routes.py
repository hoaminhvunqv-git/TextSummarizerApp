import io
import pytest
from unittest.mock import patch, MagicMock
from backend.app import create_app
from backend.config import Config


@pytest.fixture
def app():
    """Tạo Flask app test."""
    app = create_app(Config)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Tạo test client."""
    return app.test_client()


class TestOcrEndpoint:
    """Kiểm thử POST /api/v1/ocr."""

    def test_ocr_success_jpeg(self, client):
        """OCR thành công với ảnh JPEG."""
        # Mock OCR service
        with patch("backend.routes.ocr_routes.OcrService.extract_text") as mock_ocr:
            mock_ocr.return_value = {"text": "Xin chào thế giới", "char_count": 18}
            
            # Tạo ảnh giả
            image_data = b"\xff\xd8\xff\xe0" + b"\x00" * 1000  # JPEG header + data
            data = {"image": (io.BytesIO(image_data), "test.jpg")}
            
            response = client.post(
                "/api/v1/ocr",
                data=data,
                content_type="multipart/form-data",
                headers={
                    "X-Device-ID": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
                    "X-App-Version": "1.0.0",
                },
            )
            
            assert response.status_code == 200
            result = response.get_json()
            assert result["success"] is True
            assert result["data"]["text"] == "Xin chào thế giới"
            assert result["data"]["char_count"] == 18

    def test_ocr_success_png(self, client):
        """OCR thành công với ảnh PNG."""
        with patch("backend.routes.ocr_routes.OcrService.extract_text") as mock_ocr:
            mock_ocr.return_value = {"text": "Test text", "char_count": 9}
            
            image_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1000
            data = {"image": (io.BytesIO(image_data), "test.png")}
            
            response = client.post(
                "/api/v1/ocr",
                data=data,
                content_type="multipart/form-data",
                headers={
                    "X-Device-ID": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
                    "X-App-Version": "1.0.0",
                },
            )
            
            assert response.status_code == 200

    def test_ocr_missing_image_field(self, client):
        """Thiếu field 'image' → 400 VALIDATION_ERROR."""
        response = client.post(
            "/api/v1/ocr",
            data={},
            content_type="multipart/form-data",
            headers={
                "X-Device-ID": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
                "X-App-Version": "1.0.0",
            },
        )
        
        assert response.status_code == 400
        result = response.get_json()
        assert result["error_code"] == "VALIDATION_ERROR"

    def test_ocr_empty_file(self, client):
        """File rỗng → 400 FILE_EMPTY."""
        data = {"image": (io.BytesIO(b""), "empty.jpg")}
        
        response = client.post(
            "/api/v1/ocr",
            data=data,
            content_type="multipart/form-data",
            headers={
                "X-Device-ID": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
                "X-App-Version": "1.0.0",
            },
        )
        
        assert response.status_code == 400
        result = response.get_json()
        assert result["error_code"] == "FILE_EMPTY"

    def test_ocr_unsupported_format(self, client):
        """Định dạng không hỗ trợ → 400 FILE_UNSUPPORTED."""
        image_data = b"GIF89a" + b"\x00" * 1000
        data = {"image": (io.BytesIO(image_data), "test.gif")}
        
        response = client.post(
            "/api/v1/ocr",
            data=data,
            content_type="multipart/form-data",
            headers={
                "X-Device-ID": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
                "X-App-Version": "1.0.0",
            },
        )
        
        assert response.status_code == 400
        result = response.get_json()
        assert result["error_code"] == "FILE_UNSUPPORTED"

    def test_ocr_file_too_large(self, client):
        """Ảnh vượt 4MB → 413 FILE_TOO_LARGE."""
        # Tạo ảnh 5MB
        image_data = b"\xff\xd8\xff\xe0" + b"\x00" * (5 * 1024 * 1024)
        data = {"image": (io.BytesIO(image_data), "big.jpg")}
        
        response = client.post(
            "/api/v1/ocr",
            data=data,
            content_type="multipart/form-data",
            headers={
                "X-Device-ID": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
                "X-App-Version": "1.0.0",
            },
        )
        
        assert response.status_code == 413
        result = response.get_json()
        assert result["error_code"] == "FILE_TOO_LARGE"

    def test_ocr_no_text_detected(self, client):
        """Không nhận diện được chữ → 400 OCR_NO_TEXT."""
        from backend.utils.errors import AppError, ErrorCode
        
        with patch("backend.routes.ocr_routes.OcrService.extract_text") as mock_ocr:
            mock_ocr.side_effect = AppError(ErrorCode.OCR_NO_TEXT)
            
            image_data = b"\xff\xd8\xff\xe0" + b"\x00" * 1000
            data = {"image": (io.BytesIO(image_data), "blank.jpg")}
            
            response = client.post(
                "/api/v1/ocr",
                data=data,
                content_type="multipart/form-data",
                headers={
                    "X-Device-ID": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
                    "X-App-Version": "1.0.0",
                },
            )
            
            assert response.status_code == 400
            result = response.get_json()
            assert result["error_code"] == "OCR_NO_TEXT"

    def test_ocr_missing_device_id(self, client):
        """Thiếu X-Device-ID → 400 INVALID_DEVICE_ID."""
        image_data = b"\xff\xd8\xff\xe0" + b"\x00" * 1000
        data = {"image": (io.BytesIO(image_data), "test.jpg")}
        
        response = client.post(
            "/api/v1/ocr",
            data=data,
            content_type="multipart/form-data",
            headers={"X-App-Version": "1.0.0"},
        )
        
        assert response.status_code == 400
        result = response.get_json()
        assert result["error_code"] == "INVALID_DEVICE_ID"

    def test_ocr_invalid_device_id(self, client):
        """X-Device-ID không hợp lệ → 400 INVALID_DEVICE_ID."""
        image_data = b"\xff\xd8\xff\xe0" + b"\x00" * 1000
        data = {"image": (io.BytesIO(image_data), "test.jpg")}
        
        response = client.post(
            "/api/v1/ocr",
            data=data,
            content_type="multipart/form-data",
            headers={
                "X-Device-ID": "not-a-uuid",
                "X-App-Version": "1.0.0",
            },
        )
        
        assert response.status_code == 400
        result = response.get_json()
        assert result["error_code"] == "INVALID_DEVICE_ID"

    def test_ocr_old_app_version(self, client):
        """X-App-Version cũ → 426 UPDATE_REQUIRED."""
        image_data = b"\xff\xd8\xff\xe0" + b"\x00" * 1000
        data = {"image": (io.BytesIO(image_data), "test.jpg")}
        
        response = client.post(
            "/api/v1/ocr",
            data=data,
            content_type="multipart/form-data",
            headers={
                "X-Device-ID": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
                "X-App-Version": "0.9.0",
            },
        )
        
        assert response.status_code == 426
        result = response.get_json()
        assert result["error_code"] == "UPDATE_REQUIRED"

    def test_ocr_rate_limit(self, client):
        """Vượt 20 lượt OCR/ngày/IP → 429 RATE_LIMITED (không gọi Gemini thật)."""
        from backend.extensions import limiter

        limiter.reset()
        image_data = b"\xff\xd8\xff\xe0" + b"\x00" * 1000
        headers = {
            "X-Device-ID": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
            "X-App-Version": "1.0.0",
        }

        with patch(
            "backend.routes.ocr_routes.OcrService.extract_text",
            return_value={"text": "ok", "char_count": 2},
        ):
            codes = []
            overflow = None
            for _ in range(21):
                response = client.post(
                    "/api/v1/ocr",
                    data={"image": (io.BytesIO(image_data), "test.jpg")},
                    content_type="multipart/form-data",
                    headers=headers,
                )
                codes.append(response.status_code)
                if response.status_code == 429:
                    overflow = response

        try:
            assert codes[:20] == [200] * 20
            assert overflow is not None, "Lượt thứ 21 phải bị chặn rate limit"
            assert overflow.get_json()["error_code"] == "RATE_LIMITED"
        finally:
            limiter.reset()
