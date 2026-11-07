import io
from pathlib import Path

from docx import Document
from pypdf import PdfReader

try:
    from backend.utils.errors import AppError, ErrorCode
    from backend.utils.text_utils import normalize_text
except ImportError:
    from utils.errors import AppError, ErrorCode
    from utils.text_utils import normalize_text

SUPPORTED_EXTENSIONS = {".txt", ".docx", ".pdf"}

# SPEC 5.2: thử UTF-8 trước, latin-1 luôn giải mã được nên là chốt cuối
TXT_ENCODINGS = ("utf-8", "utf-8-sig", "cp1258", "latin-1")


def _extract_txt(content: bytes) -> str:
    for encoding in TXT_ENCODINGS:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise AppError(ErrorCode.FILE_EMPTY)


def _extract_docx(content: bytes) -> str:
    try:
        document = Document(io.BytesIO(content))
        parts = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
    except Exception:
        raise AppError(
            ErrorCode.FILE_UNSUPPORTED,
            message="Không đọc được file .docx. File có thể bị hỏng hoặc sai định dạng.",
        )
    return "\n".join(parts)


def _extract_pdf(content: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        raise AppError(ErrorCode.PDF_SCANNED)
    if not normalize_text(text):
        raise AppError(ErrorCode.PDF_SCANNED)
    return text


def extract_text(filename: str, content: bytes) -> str:
    """Trích văn bản từ TXT/DOCX/PDF và chuẩn hóa NFC + strip (SPEC 5.2)."""
    extension = Path(filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise AppError(ErrorCode.FILE_UNSUPPORTED)
    if not content:
        raise AppError(ErrorCode.FILE_EMPTY)

    if extension == ".txt":
        text = _extract_txt(content)
    elif extension == ".docx":
        text = _extract_docx(content)
    else:
        text = _extract_pdf(content)

    text = normalize_text(text)
    if not text:
        raise AppError(ErrorCode.FILE_EMPTY)
    return text