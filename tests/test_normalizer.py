import unittest

from src.normalizer import (
    amounts_close,
    normalize_amount,
    normalize_date,
    normalize_digits,
    normalize_inn,
    normalize_kpp,
    normalize_org_name,
    normalize_single_line,
    normalize_text,
    normalize_unit,
)


class TestNormalizer(unittest.TestCase):
    def test_text_normalization_preserves_lines(self):
        self.assertEqual(normalize_text("  А\n\n\n  Б  "), "А\n\nБ")

    def test_single_line(self):
        self.assertEqual(
            normalize_single_line("  ООО   Ромашка\nИНН  7701234567 "),
            "ООО Ромашка ИНН 7701234567",
        )

    def test_digits(self):
        self.assertEqual(normalize_digits("ИНН 770 123-45-67"), "7701234567")

    def test_inn_kpp(self):
        self.assertEqual(normalize_inn("ИНН 770 123 4567"), "7701234567")
        self.assertEqual(normalize_inn("770123456789"), "770123456789")
        self.assertIsNone(normalize_inn("123"))
        self.assertEqual(normalize_kpp("КПП 770 101 001"), "770101001")
        self.assertIsNone(normalize_kpp("77010100"))

    def test_amount_ru_decimal(self):
        self.assertEqual(normalize_amount("12 345,67 руб."), 12345.67)

    def test_amount_en_decimal(self):
        self.assertEqual(normalize_amount("12,345.67"), 12345.67)

    def test_amount_dot_thousands_comma_decimal(self):
        self.assertEqual(normalize_amount("25.500,50"), 25500.50)

    def test_amount_plain_integer(self):
        self.assertEqual(normalize_amount("1 000"), 1000.0)

    def test_amount_rub_kop(self):
        self.assertEqual(normalize_amount("25 500 руб. 50 коп."), 25500.50)

    def test_amount_dash_kop(self):
        self.assertEqual(normalize_amount("25500-50"), 25500.50)

    def test_bad_amount(self):
        self.assertIsNone(normalize_amount("abc"))

    def test_dates_numeric(self):
        self.assertEqual(normalize_date("22.05.2026"), "2026-05-22")
        self.assertEqual(normalize_date("22/05/26"), "2026-05-22")
        self.assertEqual(normalize_date("22-05-2026"), "2026-05-22")
        self.assertEqual(normalize_date("2026-05-22"), "2026-05-22")

    def test_dates_textual(self):
        self.assertEqual(normalize_date("22 мая 2026"), "2026-05-22")
        self.assertEqual(normalize_date("«22» мая 2026 г."), "2026-05-22")
        self.assertEqual(normalize_date("22 мая 26 года"), "2026-05-22")

    def test_bad_date(self):
        self.assertIsNone(normalize_date("99.99.9999"))

    def test_org_name(self):
        self.assertEqual(
            normalize_org_name(" ООО «Ромашка», ИНН 7701234567 "),
            "ООО «Ромашка",
        )

    def test_unit(self):
        self.assertEqual(normalize_unit("шт."), "шт")
        self.assertEqual(normalize_unit("М²"), "м2")

    def test_amounts_close(self):
        self.assertTrue(amounts_close(1000.0, 1000.01, tolerance=0.02))
        self.assertFalse(amounts_close(1000.0, 1001.0, tolerance=0.02))


if __name__ == "__main__":
    unittest.main()
