import unittest

from validation.splits import walk_forward


class SplitTests(unittest.TestCase):
    """AT-STAT-06: deterministic split generation."""

    def test_06a_deterministic(self):
        first = walk_forward(1000, 200, 100, step=100, purge=10, embargo=5)
        second = walk_forward(1000, 200, 100, step=100, purge=10, embargo=5)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 7)

    def test_06b_no_overlap_and_order(self):
        for split in walk_forward(1000, 200, 100, step=100, purge=10, embargo=5):
            train, test = split.train(), split.test()
            self.assertTrue(train and test)
            self.assertLess(max(train), min(test))
            self.assertEqual(len(set(train) & set(test)), 0)

    def test_06c_test_windows_advance_without_overlap(self):
        splits = walk_forward(1000, 200, 100, step=100)
        tests = [s.test() for s in splits]
        for previous, current in zip(tests, tests[1:]):
            self.assertEqual(max(previous) + 1, min(current))
        self.assertEqual(splits[0].test_start, 200)
        self.assertEqual(splits[-1].test_stop, 1000)

    def test_06e_purge_and_embargo(self):
        split = walk_forward(500, 200, 100, purge=10, embargo=5)[0]
        self.assertEqual(split.train_stop - split.train_start, 190)
        self.assertEqual(split.test_start - split.train_stop, 15)
        self.assertEqual(split.gap, 15)

    def test_06f_invalid_parameters(self):
        for kwargs in ({"n": 0}, {"train_size": 0}, {"test_size": 0}, {"purge": -1},
                       {"embargo": -1}, {"purge": 200}, {"step": 0}):
            params = {"n": 1000, "train_size": 200, "test_size": 100}
            params.update(kwargs)
            with self.assertRaises(ValueError):
                walk_forward(**params)

    def test_too_short_series_returns_empty(self):
        self.assertEqual(walk_forward(150, 200, 100), [])


if __name__ == "__main__":
    unittest.main()