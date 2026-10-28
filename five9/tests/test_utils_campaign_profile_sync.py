import unittest

from five9.utils.campaign_profile_sync import (
    ACTION_CREATE,
    ACTION_SKIP_EXISTS,
    ACTION_SKIP_IDENTICAL,
    ACTION_UPDATE,
    criteria_for_write,
    filters_match,
    plan_profile,
    profile_differences,
    select_profiles,
)


def make_filter(right="Business", expression="1"):
    return {
        "crmCriteria": [
            {"leftValue": "vertical", "compareOperator": "Equals", "rightValue": right}
        ],
        "grouping": {"expression": expression, "type": "Custom"},
    }


class SelectProfilesTests(unittest.TestCase):
    def test_matches_any_word_case_insensitively(self):
        profiles = [
            {"name": "oDEM Business A"},
            {"name": "x TECHNOLOGY"},
            {"name": "Default"},
        ]
        names = [
            p["name"] for p in select_profiles(profiles, ["business", "Technology"])
        ]
        self.assertEqual(names, ["oDEM Business A", "x TECHNOLOGY"])


class DifferenceTests(unittest.TestCase):
    def test_none_values_are_ignored(self):
        self.assertEqual(profile_differences({"a": 1, "b": None}, {"a": 1}), [])

    def test_reports_changed_keys(self):
        self.assertEqual(profile_differences({"a": 1, "b": 2}, {"a": 1, "b": 3}), ["b"])

    def test_filters_match_treats_none_and_empty_right_value_alike(self):
        self.assertTrue(filters_match(make_filter(right=None), make_filter(right="")))

    def test_filters_match_ignores_whitespace_in_expression(self):
        self.assertTrue(
            filters_match(
                make_filter(expression="1  AND 2"), make_filter(expression="1 AND 2")
            )
        )
        self.assertFalse(filters_match(make_filter(right="A"), make_filter(right="B")))

    def test_criteria_for_write_fills_none(self):
        self.assertEqual(
            criteria_for_write(make_filter(right=None)["crmCriteria"])[0]["rightValue"],
            "",
        )


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.profile = {"name": "p", "ANI": "1"}
        self.filter = make_filter()

    def test_create_when_missing(self):
        self.assertEqual(
            plan_profile(self.profile, self.filter, None, None, False)[0], ACTION_CREATE
        )

    def test_skip_identical(self):
        result = plan_profile(
            self.profile, self.filter, dict(self.profile), make_filter(), False
        )
        self.assertEqual(result[0], ACTION_SKIP_IDENTICAL)

    def test_differs_without_overwrite_is_skipped(self):
        action, diffs = plan_profile(
            self.profile, self.filter, {"name": "p", "ANI": "2"}, make_filter(), False
        )
        self.assertEqual(action, ACTION_SKIP_EXISTS)
        self.assertEqual(diffs, ["profile field ANI"])

    def test_differs_with_overwrite_updates(self):
        action, diffs = plan_profile(
            self.profile,
            self.filter,
            dict(self.profile),
            make_filter(right="Other"),
            True,
        )
        self.assertEqual(action, ACTION_UPDATE)
        self.assertEqual(diffs, ["filter"])


if __name__ == "__main__":
    unittest.main()
