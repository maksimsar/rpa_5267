import unittest

from src.parser import (
    extract_table_rows_from_vision_response,
    extract_text_from_vision_response,
    parse_requisites,
    parse_requisites_simple,
)


SAMPLE_TEXT = """
Счёт на оплату № ABC-123 от 22.05.2026

Поставщик: ООО «Ромашка» ИНН 7701234567 КПП 770101001
Покупатель: ООО «Василек» ИНН 7812345678 КПП 781201001

№ Наименование Кол-во Ед. Цена Сумма
1 Услуга разработки 2 шт 10 000,00 20 000,00
2 Поддержка проекта 1 усл 5 500,50 5 500,50

Итого к оплате: 25 500,50 руб.
"""


class TestParserHappyPath(unittest.TestCase):
    def test_parse_full_document_explainable(self):
        result = parse_requisites(SAMPLE_TEXT)

        self.assertTrue(result["success"])
        self.assertEqual(result["document"]["type"]["value"], "Счёт")
        self.assertEqual(result["document"]["number"]["value"], "ABC-123")
        self.assertEqual(result["document"]["date"]["value"], "2026-05-22")
        self.assertEqual(result["document"]["total_amount"]["value"], 25500.50)

        self.assertGreaterEqual(len(result["counterparties"]), 2)
        self.assertEqual(result["counterparties"][0]["inn"]["value"], "7701234567")
        self.assertEqual(result["counterparties"][0]["kpp"]["value"], "770101001")
        self.assertEqual(result["counterparties"][0]["role"], "seller")
        self.assertEqual(result["counterparties"][1]["role"], "buyer")

        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["name"]["value"], "Услуга разработки")
        self.assertEqual(result["items"][0]["quantity"]["value"], 2.0)
        self.assertEqual(result["items"][0]["price"]["value"], 10000.0)
        self.assertEqual(result["items"][0]["amount"]["value"], 20000.0)
        self.assertEqual(result["items"][0]["unit"]["value"], "шт")

    def test_parse_simple(self):
        result = parse_requisites_simple(SAMPLE_TEXT)
        self.assertEqual(result["document"]["type"], "Счёт")
        self.assertEqual(result["document"]["number"], "ABC-123")
        self.assertEqual(result["document"]["date"], "2026-05-22")
        self.assertEqual(result["document"]["total_amount"], 25500.50)


class TestParserDocumentTypes(unittest.TestCase):
    def assert_doc(self, text, expected_type, expected_number):
        result = parse_requisites(text)
        self.assertEqual(result["document"]["type"]["value"], expected_type)
        self.assertEqual(result["document"]["number"]["value"], expected_number)

    def test_invoice_variants(self):
        self.assert_doc("Счет на оплату № 1 от 22.05.2026 Итого: 100", "Счёт", "1")
        self.assert_doc("Счёт на оплату № INV-22/5 от 22.05.2026 Итого: 100", "Счёт", "INV-22/5")

    def test_act_number_not_word(self):
        self.assert_doc("Акт выполненных работ № 55 от 22.05.2026 Итого: 1000", "Акт", "55")

    def test_delivery_note(self):
        self.assert_doc("Товарная накладная № TN-3 от 22.05.2026 Итого: 100", "Накладная", "TN-3")

    def test_upd(self):
        self.assert_doc("Универсальный передаточный документ № 987 от 22.05.2026 Итого: 100", "УПД", "987")

    def test_contract(self):
        self.assert_doc("Договор поставки № DOG-77/2026 от 22 мая 2026 г. на сумму 1000", "Договор", "DOG-77/2026")

    def test_invoice_factura(self):
        self.assert_doc("Счет-фактура № SF-1 от 22.05.2026 Всего: 100", "Счет-фактура", "SF-1")


class TestParserNumbersDatesAmounts(unittest.TestCase):
    def test_number_variants(self):
        variants = [
            ("Документ № 123 от 22.05.2026 Итого: 100", "123"),
            ("Номер документа: ABC-123/2026 от 22.05.2026 Итого: 100", "ABC-123/2026"),
            ("No. 321 от 22.05.2026 Итого: 100", "321"),
            ("N 777 от 22.05.2026 Итого: 100", "777"),
        ]
        for text, expected in variants:
            with self.subTest(text=text):
                self.assertEqual(parse_requisites(text)["document"]["number"]["value"], expected)

    def test_date_variants(self):
        variants = [
            "Счёт № 1 от 22.05.2026 Итого: 100",
            "Счёт № 1 от 2026-05-22 Итого: 100",
            "Счёт № 1 от 22/05/26 Итого: 100",
            "Счёт № 1 от «22» мая 2026 г. Итого: 100",
        ]
        for text in variants:
            with self.subTest(text=text):
                self.assertEqual(parse_requisites(text)["document"]["date"]["value"], "2026-05-22")

    def test_amount_variants(self):
        variants = [
            ("Итого к оплате: 25 500,50 руб.", 25500.5),
            ("Всего к оплате: 25500.50", 25500.5),
            ("Итого с НДС: 25.500,50", 25500.5),
            ("Всего наименований 2, на сумму 25 500,50", 25500.5),
            ("Итого: 25 500 руб. 50 коп.", 25500.5),
            ("Итого: 25500-50", 25500.5),
        ]
        for amount_text, expected in variants:
            with self.subTest(amount_text=amount_text):
                text = f"Счёт № 1 от 22.05.2026 {amount_text}"
                self.assertEqual(parse_requisites(text)["document"]["total_amount"]["value"], expected)

    def test_fallback_amount(self):
        text = "Счёт № 1 от 22.05.2026 Без ключевых слов 100 200 300"
        self.assertEqual(parse_requisites(text)["document"]["total_amount"]["value"], 300.0)


class TestCounterparties(unittest.TestCase):
    def test_supplier_buyer(self):
        text = """
        Счёт № 1 от 22.05.2026
        Поставщик: ООО «Ромашка» ИНН 7701234567 КПП 770101001
        Покупатель: ООО «Василек» ИНН 7812345678 КПП 781201001
        Итого: 100
        """
        result = parse_requisites(text)
        self.assertEqual(result["counterparties"][0]["role"], "seller")
        self.assertEqual(result["counterparties"][1]["role"], "buyer")

    def test_executor_customer(self):
        text = """
        Акт № 2 от 22.05.2026
        Исполнитель: ИП Иванов Иван Иванович ИНН 770123456789
        Заказчик: ООО «Клиент» ИНН 7812345678 КПП 781201001
        Итого: 100
        """
        result = parse_requisites(text)
        self.assertEqual(result["counterparties"][0]["role"], "executor")
        self.assertEqual(result["counterparties"][0]["inn"]["value"], "770123456789")
        self.assertIsNone(result["counterparties"][0]["kpp"]["value"])
        self.assertEqual(result["counterparties"][1]["role"], "customer")

    def test_fallback_counterparties_by_inn(self):
        text = """
        ООО «Ромашка» ИНН 7701234567 КПП 770101001
        ООО «Василек» ИНН 7812345678 КПП 781201001
        Счёт № 1 от 22.05.2026 Итого: 100
        """
        result = parse_requisites(text)
        self.assertGreaterEqual(len(result["counterparties"]), 2)
        self.assertEqual(result["counterparties"][0]["role"], "seller")
        self.assertEqual(result["counterparties"][1]["role"], "buyer")

    def test_spaced_inn_kpp(self):
        text = """
        Счёт № 1 от 22.05.2026
        Продавец: ООО Ромашка ИНН 770 123 4567 КПП 770 101 001
        Покупатель: ООО Василек ИНН 781 234 5678 КПП 781 201 001
        Итого: 100
        """
        result = parse_requisites(text)
        self.assertEqual(result["counterparties"][0]["inn"]["value"], "7701234567")
        self.assertEqual(result["counterparties"][0]["kpp"]["value"], "770101001")


class TestItems(unittest.TestCase):
    def test_text_items_with_units(self):
        text = """
        Счёт № 1 от 22.05.2026
        1 Услуга разработки 2 шт 10 000,00 20 000,00
        2 Поддержка проекта 1 усл 5 500,50 5 500,50
        Итого: 25 500,50
        """
        result = parse_requisites(text)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["unit"]["value"], "шт")

    def test_text_item_without_row_number(self):
        text = """
        Счёт № 1 от 22.05.2026
        Услуга разработки 2 1000 2000
        Итого: 2000
        """
        result = parse_requisites(text)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["name"]["value"], "Услуга разработки")

    def test_multiline_item(self):
        text = """
        Счёт № 1 от 22.05.2026
        1 Очень длинное название услуги разработки
        продолжение названия 2 1000 2000
        Итого: 2000
        """
        result = parse_requisites(text)
        self.assertEqual(len(result["items"]), 1)
        self.assertIn("Очень длинное название", result["items"][0]["name"]["value"])

    def test_skip_totals_as_items(self):
        text = """
        Счёт № 1 от 22.05.2026
        Итого 2 1000 2000
        Итого: 2000
        """
        result = parse_requisites(text)
        self.assertEqual(len(result["items"]), 0)


class TestVisionExtraction(unittest.TestCase):
    def test_full_text_priority_no_duplicates(self):
        response = {
            "fullText": "Счёт № 1 от 22.05.2026\nИтого: 100",
            "pages": [
                {"blocks": [{"lines": [{"text": "Счёт № 1 от 22.05.2026"}, {"text": "Итого: 100"}]}]}
            ],
        }
        text = extract_text_from_vision_response(response)
        self.assertEqual(text.count("Счёт"), 1)

    def test_line_extraction(self):
        response = {
            "results": [
                {
                    "textDetection": {
                        "pages": [
                            {
                                "blocks": [
                                    {"lines": [{"text": "Акт № 55 от 2026-05-22"}]},
                                    {"lines": [{"text": "Итого: 1000,00"}]},
                                ]
                            }
                        ]
                    }
                }
            ]
        }
        result = parse_requisites(response)
        self.assertEqual(result["document"]["type"]["value"], "Акт")
        self.assertEqual(result["document"]["number"]["value"], "55")
        self.assertEqual(result["document"]["date"]["value"], "2026-05-22")
        self.assertEqual(result["document"]["total_amount"]["value"], 1000.0)

    def test_word_extraction(self):
        response = {"pages": [{"blocks": [{"lines": [{"words": [{"text": "Счёт"}, {"text": "№"}, {"text": "1"}]}]}]}]}
        self.assertIn("Счёт", extract_text_from_vision_response(response))

    def test_table_rows_extraction_cells(self):
        response = {
            "tables": [
                {
                    "cells": [
                        {"rowIndex": 0, "columnIndex": 0, "text": "Наименование"},
                        {"rowIndex": 0, "columnIndex": 1, "text": "Кол-во"},
                        {"rowIndex": 0, "columnIndex": 2, "text": "Цена"},
                        {"rowIndex": 0, "columnIndex": 3, "text": "Сумма"},
                        {"rowIndex": 1, "columnIndex": 0, "text": "Услуга"},
                        {"rowIndex": 1, "columnIndex": 1, "text": "2"},
                        {"rowIndex": 1, "columnIndex": 2, "text": "1000"},
                        {"rowIndex": 1, "columnIndex": 3, "text": "2000"},
                    ]
                }
            ]
        }
        rows = extract_table_rows_from_vision_response(response)
        self.assertEqual(rows[1][0], "Услуга")

    def test_parse_items_from_table_cells(self):
        response = {
            "fullText": "Счёт № 1 от 22.05.2026\nИтого: 2000",
            "tables": [
                {
                    "cells": [
                        {"rowIndex": 0, "columnIndex": 0, "text": "Наименование"},
                        {"rowIndex": 0, "columnIndex": 1, "text": "Количество"},
                        {"rowIndex": 0, "columnIndex": 2, "text": "Цена"},
                        {"rowIndex": 0, "columnIndex": 3, "text": "Сумма"},
                        {"rowIndex": 1, "columnIndex": 0, "text": "Услуга"},
                        {"rowIndex": 1, "columnIndex": 1, "text": "2"},
                        {"rowIndex": 1, "columnIndex": 2, "text": "1000"},
                        {"rowIndex": 1, "columnIndex": 3, "text": "2000"},
                    ]
                }
            ],
        }
        result = parse_requisites(response)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["name"]["value"], "Услуга")
        self.assertEqual(result["items"][0]["amount"]["value"], 2000.0)


class TestSafetyAndEdgeCases(unittest.TestCase):
    def test_empty_text_does_not_crash(self):
        result = parse_requisites("")
        self.assertTrue(result["success"])
        self.assertIsNone(result["document"]["type"]["value"])
        self.assertGreater(len(result["warnings"]), 0)

    def test_none_does_not_crash(self):
        result = parse_requisites(None)
        self.assertTrue(result["success"])
        self.assertGreater(len(result["warnings"]), 0)

    def test_empty_dict_does_not_crash(self):
        result = parse_requisites({})
        self.assertTrue(result["success"])
        self.assertGreater(len(result["warnings"]), 0)

    def test_unexpected_dict_does_not_crash(self):
        result = parse_requisites({"unexpected": {"data": [1, 2, 3]}})
        self.assertTrue(result["success"])
        self.assertGreater(len(result["warnings"]), 0)

    def test_unknown_document_warns(self):
        result = parse_requisites("Просто текст без реквизитов")
        self.assertTrue(result["success"])
        self.assertIn("Не удалось определить тип документа", result["warnings"])


if __name__ == "__main__":
    unittest.main()
