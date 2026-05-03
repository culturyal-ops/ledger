"""
GoldVault Ledger - Calculation Tests
Run this file to verify all calculation logic is correct.
"""

import unittest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.calculations import (
    floor_3d, ceil_3d, to_995_basis, format_decimal, compute_balance
)


class TestCalculations(unittest.TestCase):
    """Test suite for GoldVault calculation functions."""

    def test_floor_3d(self):
        """Test floor rounding to 3 decimal places."""
        self.assertEqual(floor_3d(9.70868), 9.708)
        self.assertEqual(floor_3d(10.0), 10.0)
        self.assertEqual(floor_3d(0.0009), 0.0)
        self.assertEqual(floor_3d(1.9999), 1.999)
        self.assertEqual(floor_3d(100.4567), 100.456)

    def test_ceil_3d(self):
        """Test ceiling rounding to 3 decimal places."""
        self.assertEqual(ceil_3d(9.70868), 9.709)
        self.assertEqual(ceil_3d(10.0), 10.0)
        self.assertEqual(ceil_3d(0.0001), 0.001)
        self.assertEqual(ceil_3d(1.9991), 2.0)
        self.assertEqual(ceil_3d(100.4561), 100.457)

    def test_format_decimal(self):
        """Test decimal formatting (strip trailing zeros)."""
        self.assertEqual(format_decimal(9.708), "9.708")
        self.assertEqual(format_decimal(10.04), "10.04")
        self.assertEqual(format_decimal(100.4), "100.4")
        self.assertEqual(format_decimal(10.0), "10")
        self.assertEqual(format_decimal(9.709), "9.709")
        self.assertEqual(format_decimal(0.100), "0.1")

    def test_purity_percentage(self):
        """Test conversion with purity as percentage (<=100)."""
        # purity=99.9 (percentage) -> factor=0.999
        result = to_995_basis(10.0, 99.9, 'Smith to Moozhayil')
        expected_raw = 10.0 * (99.9 / 100.0) / 0.995
        self.assertEqual(result, floor_3d(expected_raw))
        self.assertAlmostEqual(result, 10.040, places=3)

    def test_purity_fineness(self):
        """Test conversion with purity as fineness (>100)."""
        # purity=995 (fineness) -> factor=0.995
        result = to_995_basis(10.0, 995, 'Smith to Moozhayil')
        expected_raw = 10.0 * (995 / 1000.0) / 0.995
        self.assertEqual(result, floor_3d(expected_raw))
        # 10 * 0.995 / 0.995 = 10.0 exactly
        self.assertEqual(result, 10.0)

    def test_purity_100_percentage(self):
        """Test conversion with 100% purity."""
        # purity=100 -> factor=1.0
        result = to_995_basis(10.0, 100, 'Moozhayil to Smith')
        expected_raw = 10.0 * 1.0 / 0.995
        self.assertEqual(result, ceil_3d(expected_raw))
        self.assertAlmostEqual(result, 10.051, places=3)

    def test_direction_floor(self):
        """Test that 'Smith to Moozhayil' uses floor rounding."""
        result = to_995_basis(10.0, 99.5, 'Smith to Moozhayil')
        raw = 10.0 * (99.5 / 100.0) / 0.995
        self.assertEqual(result, floor_3d(raw))
        # Verify it's actually floored (less than or equal to raw)
        self.assertLessEqual(result, raw)

    def test_direction_ceil(self):
        """Test that 'Moozhayil to Smith' uses ceiling rounding."""
        result = to_995_basis(10.0, 99.5, 'Moozhayil to Smith')
        raw = 10.0 * (99.5 / 100.0) / 0.995
        self.assertEqual(result, ceil_3d(raw))
        # Verify it's actually ceiled
        self.assertGreaterEqual(result, raw)

    def test_invalid_weight(self):
        """Test that invalid weights raise ValueError."""
        with self.assertRaises(ValueError):
            to_995_basis(0, 99.5, 'Smith to Moozhayil')
        with self.assertRaises(ValueError):
            to_995_basis(-1, 99.5, 'Smith to Moozhayil')

    def test_invalid_purity(self):
        """Test that invalid purity values raise ValueError."""
        with self.assertRaises(ValueError):
            to_995_basis(10.0, 0, 'Smith to Moozhayil')
        with self.assertRaises(ValueError):
            to_995_basis(10.0, -1, 'Smith to Moozhayil')
        with self.assertRaises(ValueError):
            to_995_basis(10.0, 1001, 'Smith to Moozhayil')

    def test_invalid_direction(self):
        """Test that invalid direction raises ValueError."""
        with self.assertRaises(ValueError):
            to_995_basis(10.0, 99.5, 'invalid')
        with self.assertRaises(ValueError):
            to_995_basis(10.0, 99.5, 'Smith to Smith')

    def test_example_values_from_spec(self):
        """Test the specific examples from the specification."""
        # 9.70868 -> ceiling: 9.709, floor: 9.708
        self.assertEqual(ceil_3d(9.70868), 9.709)
        self.assertEqual(floor_3d(9.70868), 9.708)
        
        # 10.04 -> 10.04 (no trailing zero)
        self.assertEqual(format_decimal(10.04), "10.04")
        
        # 100.4 -> 100.4
        self.assertEqual(format_decimal(100.4), "100.4")

    def test_compute_balance(self):
        """Test balance computation for a series of entries."""
        entries = [
            {'raw_weight': 10.0, 'purity': 995, 'direction': 'Moozhayil to Smith'},
            {'raw_weight': 5.0, 'purity': 995, 'direction': 'Smith to Moozhayil'},
            {'raw_weight': 3.0, 'purity': 995, 'direction': 'Moozhayil to Smith'},
        ]
        results = compute_balance(entries)
        
        self.assertEqual(len(results), 3)
        
        # First: Moozhayil to Smith, 10g at 995 -> ceil(10.0) = 10.0, balance = 10.0
        self.assertEqual(results[0][0], 10.0)
        self.assertEqual(results[0][1], 10.0)
        
        # Second: Smith to Moozhayil, 5g at 995 -> floor(5.0) = 5.0, balance = 5.0
        self.assertEqual(results[1][0], 5.0)
        self.assertEqual(results[1][1], 5.0)
        
        # Third: Moozhayil to Smith, 3g at 995 -> ceil(3.0) = 3.0, balance = 8.0
        self.assertEqual(results[2][0], 3.0)
        self.assertEqual(results[2][1], 8.0)

    def test_edge_case_very_small_weight(self):
        """Test with very small weight values."""
        result = to_995_basis(0.001, 995, 'Smith to Moozhayil')
        self.assertGreater(result, 0)
        self.assertLessEqual(result, 0.001)

    def test_edge_case_very_high_weight(self):
        """Test with large weight values."""
        result = to_995_basis(1000.0, 995, 'Moozhayil to Smith')
        self.assertAlmostEqual(result, 1000.0, places=3)

    def test_purity_boundary_100(self):
        """Test purity exactly at 100 (boundary between percentage and fineness)."""
        result_percent = to_995_basis(10.0, 100, 'Smith to Moozhayil')
        # 100 is treated as percentage: factor = 100/100 = 1.0
        expected = floor_3d(10.0 * 1.0 / 0.995)
        self.assertEqual(result_percent, expected)

    def test_purity_just_above_100(self):
        """Test purity just above 100 (should be treated as fineness)."""
        result_fineness = to_995_basis(10.0, 101, 'Smith to Moozhayil')
        # 101 is treated as fineness: factor = 101/1000 = 0.101
        expected = floor_3d(10.0 * 0.101 / 0.995)
        self.assertEqual(result_fineness, expected)

    def test_realistic_scenario(self):
        """Test a realistic gold transaction scenario."""
        # Smith gives 50g of 22K gold (91.6% purity)
        weight = 50.0
        purity = 91.6
        direction = 'Smith to Moozhayil'
        
        result = to_995_basis(weight, purity, direction)
        
        # Expected: 50 * 0.916 / 0.995 = 46.030... -> floor = 46.030
        expected_raw = 50.0 * 0.916 / 0.995
        self.assertEqual(result, floor_3d(expected_raw))
        self.assertAlmostEqual(result, 46.030, places=3)

    def test_balance_with_mixed_purities(self):
        """Test balance calculation with different purities."""
        entries = [
            {'raw_weight': 10.0, 'purity': 99.9, 'direction': 'Moozhayil to Smith'},
            {'raw_weight': 5.0, 'purity': 995, 'direction': 'Smith to Moozhayil'},
        ]
        results = compute_balance(entries)
        
        # First entry: 10 * 0.999 / 0.995 = 10.040... -> ceil = 10.041
        self.assertAlmostEqual(results[0][0], 10.041, places=3)
        self.assertAlmostEqual(results[0][1], 10.041, places=3)
        
        # Second entry: 5 * 0.995 / 0.995 = 5.0 -> floor = 5.0
        self.assertEqual(results[1][0], 5.0)
        # Balance: 10.041 - 5.0 = 5.041
        self.assertAlmostEqual(results[1][1], 5.041, places=3)


def run_tests():
    """Run all tests and print results."""
    print("=" * 70)
    print("GoldVault Ledger - Calculation Tests")
    print("=" * 70)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCalculations)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✓ ALL TESTS PASSED")
        print(f"  Ran {result.testsRun} tests successfully")
    else:
        print("✗ SOME TESTS FAILED")
        print(f"  Failures: {len(result.failures)}")
        print(f"  Errors: {len(result.errors)}")
    print("=" * 70)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
