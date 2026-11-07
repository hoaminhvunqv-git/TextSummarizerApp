import numpy as np
from typing import Dict, Any, List
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from backend.utils.text_utils import (
        normalize_text,
        split_sentences,
        detect_language,
    )
except ImportError:
    from utils.text_utils import (
        normalize_text,
        split_sentences,
        detect_language,
    )


class TfidfService:
    """Dịch vụ tóm tắt dự phòng (fallback) sử dụng thuật toán TF-IDF theo SPEC 5.6.

    Độc lập với Gemini AI, hoạt động offline khi AI gặp lỗi/timeout/hạn mức.
    """

    @staticmethod
    def _calculate_target_sentences(total: int, length: str) -> int:
        """Tính số câu cần trích xuất dựa vào tổng số câu và tham số length.

        - short:  ~15% số câu (tối thiểu 2, tối đa 3)
        - medium: ~25% số câu (tối thiểu 3, tối đa 5)
        - long:   ~40% số câu (tối thiểu 4, tối đa 8)
        """
        if total <= 2:
            return total

        length_lower = (length or "medium").strip().lower()

        if length_lower == "short":
            k = round(total * 0.15)
            return max(2, min(3, k))
        elif length_lower == "long":
            k = round(total * 0.40)
            return max(4, min(8, k))
        else:  # medium mặc định
            k = round(total * 0.25)
            return max(3, min(5, k))

    @classmethod
    def summarize(cls, text: str, length: str = "medium") -> Dict[str, Any]:
        """Thực hiện tóm tắt văn bản bằng thuật toán TF-IDF.

        Quy trình:
        1. Chuẩn hóa NFC và tách câu regex.
        2. Chấm điểm độ quan trọng của từng câu bằng TF-IDF.
        3. Chọn top-k câu có điểm cao nhất.
        4. Sắp xếp lại các câu được chọn theo đúng THỨ TỰ GỐC ban đầu.
        5. Sinh title, description, summary và trả về source='tfidf'.
        """
        normalized_text = normalize_text(text)
        language = detect_language(normalized_text)
        sentences = split_sentences(normalized_text)
        total_sentences = len(sentences)

        # Nếu văn bản quá ngắn chỉ có 1-2 câu, lấy toàn bộ
        if total_sentences <= 2:
            selected_sentences = sentences
        else:
            # SPEC 5.6: Không dùng stopword tiếng Anh cho văn bản tiếng Việt
            stop_words = "english" if language == "en" else None

            # Mỗi câu được coi là 1 document trong TF-IDF
            try:
                vectorizer = TfidfVectorizer(
                    stop_words=stop_words,
                    token_pattern=r"(?u)\b\w+\b",
                )
                tfidf_matrix = vectorizer.fit_transform(sentences)
                # Điểm số của mỗi câu = tổng trọng số TF-IDF của các từ trong câu đó
                scores = np.array(tfidf_matrix.sum(axis=1)).flatten()
            except ValueError:
                # Trường hợp văn bản chỉ chứa ký tự đặc biệt/stop words
                scores = np.ones(total_sentences)

            # Xác định số lượng câu cần lấy
            k = cls._calculate_target_sentences(total_sentences, length)
            k = min(k, total_sentences)

            # Lấy top-k câu có điểm số cao nhất
            top_k_indices = sorted(range(total_sentences), key=lambda i: scores[i], reverse=True)[:k]

            # BẮT BUỘC (SPEC 5.6): Sắp xếp lại theo chỉ số ban đầu để GIỮ NGUYÊN THỨ TỰ GỐC
            sorted_indices = sorted(top_k_indices)
            selected_sentences = [sentences[i] for i in sorted_indices]

        # Ghép các câu thành đoạn tóm tắt với đánh số (phân biệt với Gemini)
        summary_text = "\n".join([f"{i+1}. {sentence}" for i, sentence in enumerate(selected_sentences)])

        # Sinh title fallback: câu đầu tiên cắt <= 60 ký tự (SPEC 5.6)
        first_sentence = sentences[0] if sentences else normalized_text
        if len(first_sentence) > 60:
            title = first_sentence[:57].rstrip() + "..."
        else:
            title = first_sentence

        # Sinh description fallback: 120 ký tự đầu của bản tóm tắt (SPEC 5.6)
        if len(summary_text) > 120:
            description = summary_text[:117].rstrip() + "..."
        else:
            description = summary_text

        return {
            "title": title,
            "description": description,
            "summary": summary_text,
            "language": language,
            "source": "tfidf",
            "original_length": len(normalized_text),
        }
