try:
    from backend.config import Config
    from backend.utils.text_utils import count_characters
except ImportError:
    from config import Config
    from utils.text_utils import count_characters

import pytest

# SPEC 5.4: N = clamp(floor(len / 130), 3, 10)


@pytest.mark.parametrize(
    "char_count,expected",
    [(400, 3), (650, 5), (1300, 10), (5000, 10)],
    ids=["400->3", "650->5", "1300->10", "5000->10"],
)
def test_so_cau_quiz_theo_vi_du_trong_do_d(char_count, expected):
    assert Config.quiz_question_count(char_count) == expected


@pytest.mark.parametrize(
    "char_count,expected",
    [
        (519, 3),
        (520, 4),
        (649, 4),
        (650, 5),
        (1299, 9),
        (1300, 10),
    ],
)
def test_so_cau_tang_dung_sau_moi_moc_130_ky_tu(char_count, expected):
    assert Config.quiz_question_count(char_count) == expected


@pytest.mark.parametrize("char_count", [0, 1, 129, 130, 399, 400])
def test_duoi_xuong_khong_bao_gio_thap_hon_3_cau(char_count):
    assert Config.quiz_question_count(char_count) == Config.QUIZ_QUESTIONS_MIN


@pytest.mark.parametrize("char_count", [1300, 1430, 30000, 250000])
def test_duoi_len_khong_bao_gio_vuot_10_cau(char_count):
    assert Config.quiz_question_count(char_count) == Config.QUIZ_QUESTIONS_MAX


def test_khong_ngoai_le_gioi_han_va_khong_giam_dan_theo_do_dai():
    previous = 0
    for char_count in range(0, 8000, 7):
        n = Config.quiz_question_count(char_count)
        assert Config.QUIZ_QUESTIONS_MIN <= n <= Config.QUIZ_QUESTIONS_MAX
        assert n >= previous, f"N giảm khi văn bản dài thêm ở {char_count} ký tự"
        previous = n


def test_dem_ky_tu_theo_nfc_chu_khong_theo_sao_chép_unicode():
    # "ấ" dạng tổ hợp = a + mũ + sắc (3 mã Unicode), sau NFC còn 1 ký tự nghiệp vụ
    text = "a\u0302\u0301" * (130 * 5)
    assert len(text) == 3 * 130 * 5
    char_count = count_characters(text)
    assert char_count == 130 * 5
    assert Config.quiz_question_count(char_count) == 5
