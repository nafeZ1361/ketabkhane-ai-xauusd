import unittest
from datetime import datetime, timezone

from xauusd_research.timezones import (AmbiguousServerTime, InvalidServerTime, dst_end, dst_start,
                                       eu_offset, to_tehran, to_utc)


class TimezoneTests(unittest.TestCase):
    def test_dst_boundaries(self):
        self.assertEqual(dst_start(2024), datetime(2024, 3, 31, 3, 0))
        self.assertEqual(dst_end(2024), datetime(2024, 10, 27, 4, 0))

    def test_winter_uses_plus_two(self):
        self.assertEqual(eu_offset(datetime(2024, 1, 15, 12, 0)).total_seconds(), 7200)

    def test_summer_uses_plus_three(self):
        self.assertEqual(eu_offset(datetime(2024, 7, 15, 12, 0)).total_seconds(), 10800)

    def test_to_utc_winter(self):
        self.assertEqual(to_utc(datetime(2024, 1, 1, 0, 0)), datetime(2023, 12, 31, 22, 0, tzinfo=timezone.utc))

    def test_to_utc_summer(self):
        self.assertEqual(to_utc(datetime(2024, 7, 1, 12, 0)), datetime(2024, 7, 1, 9, 0, tzinfo=timezone.utc))

    def test_spring_gap_is_rejected(self):
        with self.assertRaises(InvalidServerTime):
            to_utc(datetime(2024, 3, 31, 3, 30))

    def test_fall_ambiguity_is_rejected(self):
        with self.assertRaises(AmbiguousServerTime):
            to_utc(datetime(2024, 10, 27, 3, 30))

    def test_ambiguous_can_be_forced_to_standard_time(self):
        self.assertEqual(to_utc(datetime(2024, 10, 27, 3, 30), allow_ambiguous=True),
                         datetime(2024, 10, 27, 1, 30, tzinfo=timezone.utc))

    def test_fixed_policies(self):
        moment = datetime(2024, 7, 1, 12, 0)
        self.assertEqual(to_utc(moment, "fixed+2"), datetime(2024, 7, 1, 10, 0, tzinfo=timezone.utc))
        self.assertEqual(to_utc(moment, "fixed+3"), datetime(2024, 7, 1, 9, 0, tzinfo=timezone.utc))
        self.assertEqual(to_utc(moment, "utc"), datetime(2024, 7, 1, 12, 0, tzinfo=timezone.utc))

    def test_unknown_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            to_utc(datetime(2024, 1, 1), "mars")

    def test_tehran_conversion(self):
        utc = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(to_tehran(utc), datetime(2024, 1, 1, 3, 30, tzinfo=to_tehran(utc).tzinfo))


if __name__ == "__main__":
    unittest.main()