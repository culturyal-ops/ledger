"""
GoldVault Ledger - Calculation Engine
Handles all weight conversion, rounding, and formatting logic.
"""

import math


def floor_3d(x: float) -> float:
    """Floor a value to 3 decimal places."""
    return math.floor(x * 1000) / 1000


def ceil_3d(x: float) -> float:
    """Ceil a value to 3 decimal places."""
    return math.ceil(x * 1000) / 1000


def to_995_basis(raw_weight: float, purity: float, direction: str) -> float:
    """
    Convert raw weight to 995 basis weight, applying correct rounding.

    Purity auto-detection:
      - If purity <= 100: treat as percentage (factor = purity / 100)
      - If purity > 100: treat as fineness per 1000 (factor = purity / 1000)

    Conversion formula:
      converted = raw_weight * factor / 0.995

    Rounding:
      - 'Smith to Moozhayil' -> floor to 3 decimals
      - 'Moozhayil to Smith' -> ceil to 3 decimals

    Args:
        raw_weight: Weight in grams (must be > 0)
        purity: Purity value (percentage or fineness)
        direction: 'Smith to Moozhayil' or 'Moozhayil to Smith'

    Returns:
        Converted weight on 995 basis, rounded per direction rules.

    Raises:
        ValueError: If weight <= 0, purity <= 0, purity > 1000, or invalid direction.
    """
    if raw_weight <= 0:
        raise ValueError("Weight must be greater than 0.")
    if purity <= 0:
        raise ValueError("Purity must be greater than 0.")
    if purity > 1000:
        raise ValueError("Purity cannot exceed 1000.")
    if direction not in ('Smith to Moozhayil', 'Moozhayil to Smith'):
        raise ValueError(f"Invalid direction: {direction}")

    # Determine factor
    if purity <= 100:
        factor = purity / 100.0
    else:
        factor = purity / 1000.0

    # Convert to 995 basis
    converted = raw_weight * factor / 0.995

    # Apply rounding based on direction
    if direction == 'Smith to Moozhayil':
        return floor_3d(converted)
    else:  # 'Moozhayil to Smith'
        return ceil_3d(converted)


def format_decimal(value: float) -> str:
    """
    Format a decimal number for display:
    - Always show up to 3 decimal places
    - Strip trailing zeros after decimal point
    - Never use scientific notation

    Examples:
        9.708 -> "9.708"
        10.040 -> "10.04"
        100.400 -> "100.4"
        10.000 -> "10"
    """
    formatted = format(value, ".3f")
    if '.' in formatted:
        return formatted.rstrip('0').rstrip('.')
    return formatted


def compute_balance(entries: list) -> list:
    """
    Compute running balance for a list of entries (already sorted by date/time/id).

    Each entry dict must have: direction, raw_weight, purity
    Returns list of (converted_weight, balance_after) tuples.

    Balance logic:
        balance += converted_weight  if direction == 'Moozhayil to Smith'
        balance -= converted_weight  if direction == 'Smith to Moozhayil'
    """
    balance = 0.0
    results = []
    for entry in entries:
        converted = to_995_basis(
            entry['raw_weight'],
            entry['purity'],
            entry['direction']
        )
        if entry['direction'] == 'Moozhayil to Smith':
            balance += converted
        else:
            balance -= converted
        # Round balance to 3 decimal places for storage
        balance = round(balance, 3)
        results.append((converted, balance))
    return results


# ---------------------------------------------------------------------------
# Unit tests (run with: python calculations.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import unittest

    class TestCalculations(unittest.TestCase):

        def test_floor_3d(self):
            self.assertEqual(floor_3d(9.70868), 9.708)
            self.assertEqual(floor_3d(10.0), 10.0)
            self.assertEqual(floor_3d(0.0009), 0.0)
            self.assertEqual(floor_3d(1.9999), 1.999)

        def test_ceil_3d(self):
            self.assertEqual(ceil_3d(9.70868), 9.709)
            self.assertEqual(ceil_3d(10.0), 10.0)
            self.assertEqual(ceil_3d(0.0001), 0.001)
            self.assertEqual(ceil_3d(1.9991), 2.0)

        def test_format_decimal(self):
            self.assertEqual(format_decimal(9.708), "9.708")
            self.assertEqual(format_decimal(10.04), "10.04")
            self.assertEqual(format_decimal(100.4), "100.4")
            self.assertEqual(format_decimal(10.0), "10")
            self.assertEqual(format_decimal(9.709), "9.709")

        def test_purity_percentage(self):
            # purity=99.9 (percentage) -> factor=0.999
            result = to_995_basis(10.0, 99.9, 'Smith to Moozhayil')
            expected_raw = 10.0 * (99.9 / 100.0) / 0.995
            self.assertEqual(result, floor_3d(expected_raw))

        def test_purity_fineness(self):
            # purity=995 (fineness) -> factor=0.995
            result = to_995_basis(10.0, 995, 'Smith to Moozhayil')
            expected_raw = 10.0 * (995 / 1000.0) / 0.995
            self.assertEqual(result, floor_3d(expected_raw))
            # 10 * 0.995 / 0.995 = 10.0 exactly
            self.assertEqual(result, 10.0)

        def test_purity_100_percentage(self):
            # purity=100 -> factor=1.0
            result = to_995_basis(10.0, 100, 'Moozhayil to Smith')
            expected_raw = 10.0 * 1.0 / 0.995
            self.assertEqual(result, ceil_3d(expected_raw))

        def test_direction_floor(self):
            # Smith to Moozhayil -> floor
            result = to_995_basis(10.0, 99.5, 'Smith to Moozhayil')
            raw = 10.0 * (99.5 / 100.0) / 0.995
            self.assertEqual(result, floor_3d(raw))

        def test_direction_ceil(self):
            # Moozhayil to Smith -> ceil
            result = to_995_basis(10.0, 99.5, 'Moozhayil to Smith')
            raw = 10.0 * (99.5 / 100.0) / 0.995
            self.assertEqual(result, ceil_3d(raw))

        def test_invalid_weight(self):
            with self.assertRaises(ValueError):
                to_995_basis(0, 99.5, 'Smith to Moozhayil')
            with self.assertRaises(ValueError):
                to_995_basis(-1, 99.5, 'Smith to Moozhayil')

        def test_invalid_purity(self):
            with self.assertRaises(ValueError):
                to_995_basis(10.0, 0, 'Smith to Moozhayil')
            with self.assertRaises(ValueError):
                to_995_basis(10.0, 1001, 'Smith to Moozhayil')

        def test_invalid_direction(self):
            with self.assertRaises(ValueError):
                to_995_basis(10.0, 99.5, 'invalid')

        def test_example_values(self):
            # 9.70868 -> ceiling: 9.709, floor: 9.708
            self.assertEqual(ceil_3d(9.70868), 9.709)
            self.assertEqual(floor_3d(9.70868), 9.708)

        def test_compute_balance(self):
            entries = [
                {'raw_weight': 10.0, 'purity': 995, 'direction': 'Moozhayil to Smith'},
                {'raw_weight': 5.0, 'purity': 995, 'direction': 'Smith to Moozhayil'},
            ]
            results = compute_balance(entries)
            self.assertEqual(len(results), 2)
            # First: Moozhayil to Smith, 10g at 995 -> ceil(10.0) = 10.0, balance = 10.0
            self.assertEqual(results[0][0], 10.0)
            self.assertEqual(results[0][1], 10.0)
            # Second: Smith to Moozhayil, 5g at 995 -> floor(5.0) = 5.0, balance = 5.0
            self.assertEqual(results[1][0], 5.0)
            self.assertEqual(results[1][1], 5.0)

    unittest.main(verbosity=2)
