import unittest
from datetime import date

from solution.utils import normalize_phone, parse_date


class TestNormalizePhone(unittest.TestCase):

    def test_valid_phone_formats(self):
        self.assertEqual(normalize_phone("9876543210"), "+919876543210")
        self.assertEqual(normalize_phone("91-98765-43210"), "+919876543210")
        self.assertEqual(normalize_phone("09876543210"), "+919876543210")
        self.assertEqual(normalize_phone("+91 98765 43210"), "+919876543210")

    def test_invalid_phone_formats(self):
        invalid_numbers = [
            "1234567890",
            "987654321",
            "98765432101",
            "",
            "abcdefghij",
        ]

        for number in invalid_numbers:
            with self.subTest(number=number):
                with self.assertRaises(ValueError):
                    normalize_phone(number)


class TestParseDate(unittest.TestCase):

    def test_valid_date_formats(self):
        self.assertEqual(parse_date("2026-12-01"), "2026-12-01")
        self.assertEqual(parse_date("01/12/2026"), "2026-12-01")
        self.assertEqual(parse_date("01-12-2026"), "2026-12-01")
        self.assertEqual(parse_date("01-Dec-2026"), "2026-12-01")
        self.assertEqual(parse_date("01-dec-2026"), "2026-12-01")

    def test_invalid_dates(self):
        invalid_dates = [
            "31/02/2026",
            "2026-13-01",
            "32-01-2026",
            "",
            "not-a-date",
        ]

        for value in invalid_dates:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_date(value)


if __name__ == "__main__":
    unittest.main()