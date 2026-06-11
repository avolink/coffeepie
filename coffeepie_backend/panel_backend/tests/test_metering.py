"""Tests for the COFP metering core. Pure logic — no FastAPI/Firebase needed.

Run: PYTHONPATH=. python -m unittest tests.test_metering
"""

import unittest
from decimal import Decimal

from app.cofp.metering import (
    UsageSample,
    cofp_for_sample,
    slice_seconds_to_cofp,
)


class TestMetering(unittest.TestCase):
    def test_one_slice_one_minute_is_one_cofp(self):
        s = UsageSample("i1", "p1", "u1", slices=1, seconds=60, streaming=True)
        self.assertEqual(cofp_for_sample(s), Decimal("1"))

    def test_four_slices_thirty_minutes(self):
        s = UsageSample("i1", "p1", "u1", slices=4, seconds=1800, streaming=True)
        self.assertEqual(cofp_for_sample(s), Decimal("120"))

    def test_idle_vm_earns_nothing(self):
        # Powered on but no client streaming → not effectively served.
        s = UsageSample("i1", "p1", "u1", slices=8, seconds=3600, streaming=False)
        self.assertEqual(cofp_for_sample(s), Decimal("0"))

    def test_zero_slices_earns_nothing(self):
        s = UsageSample("i1", "p1", "u1", slices=0, seconds=3600, streaming=True)
        self.assertEqual(cofp_for_sample(s), Decimal("0"))

    def test_sub_minute_is_fractional_and_quantized(self):
        # 1 slice for 1 second = 1/60 COFP, quantized to the micro.
        self.assertEqual(slice_seconds_to_cofp(1), Decimal("0.016667"))

    def test_no_float_drift_accumulating_seconds(self):
        # Summing 60 one-second accruals must land within a micro of 1 COFP.
        total = sum((slice_seconds_to_cofp(1) for _ in range(60)), Decimal(0))
        self.assertTrue(abs(total - Decimal("1")) <= Decimal("0.001"))


if __name__ == "__main__":
    unittest.main()
