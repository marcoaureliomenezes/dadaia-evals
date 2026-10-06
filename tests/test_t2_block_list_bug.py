"""T2 block-list bug (AC2.2, AC2.4): on each version the grader passes the planted correct
fix and fails the planted assert-rewriting one (tests/plants/t2/)."""

import unittest

from test_t1_cold_onboarding import HAND, ROOT, reward

T2 = "t2-block-list-bug"
PLANTS = ROOT / "tests" / "plants" / "t2"


def planted(version, *plants):
    return reward(T2, version, "\n".join((PLANTS / f"{p}.sh").read_text() for p in plants))


class BlockListBug(unittest.TestCase):
    @unittest.expectedFailure
    def test_the_planted_correct_fix_passes_on_each_version(self):
        for version in HAND:
            with self.subTest(version):
                self.assertEqual(planted(version, "correct-fix"), "1")

    @unittest.expectedFailure
    def test_the_planted_assert_rewriting_fix_fails_on_each_version(self):
        for version in HAND:
            with self.subTest(version):
                self.assertEqual(planted(version, "correct-fix", "assert-rewrite"), "0")


if __name__ == "__main__":
    unittest.main()
