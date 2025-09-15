import unittest
import datetime
from five9.utils import general


class TestUtilsGeneral(unittest.TestCase):
    def test_get_random_password_defaults(self):
        pwd = general.get_random_password()
        self.assertEqual(len(pwd), 20)
        # Ensure required classes exist
        self.assertGreaterEqual(sum(c.islower() for c in pwd), 2)
        self.assertGreaterEqual(sum(c.isupper() for c in pwd), 2)
        self.assertGreaterEqual(sum(c.isdigit() for c in pwd), 2)
        self.assertGreaterEqual(sum(not c.isalnum() for c in pwd), 1)

    def test_get_random_password_custom(self):
        pwd = general.get_random_password(length=10, required_digits=1, required_lower=1, required_caps=1, required_special=1)
        self.assertEqual(len(pwd), 10)

    def test_datatype_conversion_bool(self):
        self.assertTrue(general.datatype_conversion(bool, 'true'))
        self.assertFalse(general.datatype_conversion(bool, 'False'))
        with self.assertRaises(Exception):
            general.datatype_conversion(bool, 'maybe')

    def test_datatype_conversion_numbers(self):
        self.assertEqual(general.datatype_conversion(int, '42'), 42)
        self.assertAlmostEqual(general.datatype_conversion(float, '3.14'), 3.14)

    def test_datatype_conversion_datetime(self):
        dt = general.datatype_conversion(datetime.datetime, '2024-07-04 12:30:45')
        self.assertIsInstance(dt, datetime.datetime)
        self.assertEqual(dt.year, 2024)
        # ISO format
        dt_iso = general.datatype_conversion(datetime.datetime, '2024-07-04T12:30:45')
        self.assertEqual(dt_iso.hour, 12)
        with self.assertRaises(Exception):
            general.datatype_conversion(datetime.datetime, 'not-a-date')

    def test_datatype_conversion_passthrough(self):
        val = 'sample'
        self.assertEqual(general.datatype_conversion(str, val), val)
        self.assertIsNone(general.datatype_conversion(type(None), None))


if __name__ == '__main__':
    unittest.main()
