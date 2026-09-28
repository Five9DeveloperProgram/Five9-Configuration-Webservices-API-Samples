import unittest
from five9.utils.campaign_profile_comprehension import (
    prettify,
    demystify_filter,
    remystify_filter,
    remystify_filter_in_place,
    canonical_expression,
    find_duplicate_criteria,
    renumber_expression,
    repair_duplicate_criteria,
    validate_grouping_tokens,
)


def criterion(left, operator="Equals", right="x"):
    return {
        "leftValue": left,
        "compareOperator": operator,
        "rightValue": right,
    }


class TestCampaignProfileComprehension(unittest.TestCase):
    def setUp(self):
        self.sample_profile_filter = {
            "grouping": {"expression": "1 AND (2 OR 3)", "type": "Custom"},
            "crmCriteria": [
                {
                    "leftValue": "fieldA",
                    "compareOperator": "Equals",
                    "rightValue": "abc",
                },
                {
                    "leftValue": "fieldB",
                    "compareOperator": "Greater",
                    "rightValue": "10",
                },
                {"leftValue": "fieldC", "compareOperator": "Less", "rightValue": "20"},
            ],
        }

    def test_prettify(self):
        ugly = "(A(B(C)))"
        pretty = prettify(ugly, "(", ")")
        self.assertIn("\n", pretty)

    def test_demystify_filter(self):
        result = demystify_filter(self.sample_profile_filter)
        self.assertIn("fieldA", result)
        self.assertIn("fieldB", result)
        self.assertIn("fieldC", result)

    def test_remystify_filter_round_trip(self):
        demystified = demystify_filter(self.sample_profile_filter)
        remystified = remystify_filter(demystified)
        self.assertEqual(len(remystified["crmCriteria"]), 3)
        self.assertEqual(remystified["grouping"]["type"], "Custom")
        self.assertEqual(remystified["grouping"]["expression"], "1 AND (2 OR 3)")

    def test_remystify_filter_accepts_legacy_comment_indexes(self):
        remystified = remystify_filter(
            "([fieldA ::Equals:: one]--[10] OR " "[fieldB ::NotEqual:: two]--[11])"
        )
        self.assertEqual(remystified["grouping"]["expression"], "(1 OR 2)")

    def test_remystify_filter_handles_overlapping_condition_text(self):
        remystified = remystify_filter(
            "[source ::NotEqual:: Paid Search][1] AND "
            "[source ::NotEqual:: Paid Search (Digital)][2]"
        )
        self.assertEqual(remystified["grouping"]["expression"], "1 AND 2")
        self.assertEqual(len(remystified["crmCriteria"]), 2)

    def test_remystify_filter_reuses_duplicate_criteria_index(self):
        remystified = remystify_filter(
            "[fieldA ::Equals:: one][1] OR [fieldA ::Equals:: one][1]"
        )
        self.assertEqual(remystified["grouping"]["expression"], "1 OR 1")
        self.assertEqual(len(remystified["crmCriteria"]), 1)

    def test_remystify_filter_accepts_operators_without_spaces(self):
        remystified = remystify_filter(
            "([fieldA ::Equals:: one][1]OR[fieldB ::Equals:: two][2])"
        )
        self.assertEqual(remystified["grouping"]["expression"], "(1 OR 2)")

    def test_remystify_filter_serializes_null_as_an_empty_right_value(self):
        remystified = remystify_filter(
            "[fieldA ::Equals:: null] OR [fieldB ::NotEqual:: null]"
        )
        self.assertEqual(
            remystified["crmCriteria"],
            [
                {
                    "compareOperator": "Equals",
                    "leftValue": "fieldA",
                    "rightValue": "",
                },
                {
                    "compareOperator": "NotEqual",
                    "leftValue": "fieldB",
                    "rightValue": "",
                },
            ],
        )

    def test_remystify_filter_rejects_text_outside_conditions(self):
        with self.assertRaisesRegex(ValueError, "unsupported text"):
            remystify_filter("[fieldA ::Equals:: one] AND unexpected")

    def test_grouping_validator_rejects_dangling_operator(self):
        with self.assertRaisesRegex(ValueError, "expected a criterion"):
            validate_grouping_tokens(["1", "OR"], 1)

    def test_grouping_validator_rejects_adjacent_criteria(self):
        with self.assertRaisesRegex(ValueError, "orphaned token"):
            validate_grouping_tokens(["1", "2"], 2)

    def test_grouping_validator_rejects_empty_parentheses(self):
        with self.assertRaisesRegex(ValueError, "expected a criterion"):
            validate_grouping_tokens(["(", ")"], 1)

    def test_grouping_validator_rejects_out_of_range_reference(self):
        with self.assertRaisesRegex(ValueError, "only 1 criteria exist"):
            validate_grouping_tokens(["2"], 1)

    def test_remystify_filter_in_place(self):
        test_string = "[fieldA ::Equals:: 1][1] AND [fieldB ::Greater:: 2][2]"
        result = remystify_filter_in_place(test_string)
        self.assertNotIn("[fieldA", result)


class TestDuplicateCriteriaRepair(unittest.TestCase):
    def test_clean_filter_is_left_alone(self):
        repair = repair_duplicate_criteria(
            {
                "crmCriteria": [criterion("a"), criterion("b")],
                "grouping": {"expression": "1 AND 2", "type": "Custom"},
            }
        )
        self.assertFalse(repair["changed"])

    def test_trailing_duplicate_needs_no_renumbering(self):
        repair = repair_duplicate_criteria(
            {
                "crmCriteria": [criterion("a"), criterion("b"), criterion("a")],
                "grouping": {"expression": "1 AND (2 OR 3)", "type": "Custom"},
            }
        )
        self.assertEqual(repair["rows_after"], 2)
        self.assertEqual(repair["grouping"]["expression"], "1 AND (2 OR 1)")
        self.assertTrue(repair["equivalent"])

    def test_leading_duplicate_shifts_later_rows_down(self):
        repair = repair_duplicate_criteria(
            {
                "crmCriteria": [
                    criterion("a"),
                    criterion("a"),
                    criterion("b"),
                    criterion("c"),
                ],
                "grouping": {"expression": "1 AND 2 AND 3 AND 4", "type": "Custom"},
            }
        )
        self.assertEqual(repair["rows_after"], 3)
        self.assertEqual(repair["grouping"]["expression"], "1 AND 1 AND 2 AND 3")
        self.assertTrue(repair["equivalent"])

    def test_repaired_expression_never_references_missing_rows(self):
        repair = repair_duplicate_criteria(
            {
                "crmCriteria": [criterion("a"), criterion("a"), criterion("b")],
                "grouping": {"expression": "3 OR 2", "type": "Custom"},
            }
        )
        referenced = [
            int(t) for t in repair["grouping"]["expression"].split() if t.isdigit()
        ]
        self.assertLessEqual(max(referenced), repair["rows_after"])

    def test_renumbering_does_not_corrupt_multi_digit_indexes(self):
        # A naive digit replace of 4->3 would rewrite 14 as 13.
        self.assertEqual(renumber_expression("4 AND 14", {4: 3, 14: 14}), "3 AND 14")

    def test_duplicates_are_reported_with_keep_and_drop_positions(self):
        duplicates = find_duplicate_criteria(
            {"crmCriteria": [criterion("a"), criterion("b"), criterion("a")]}
        )
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["keep"], 1)
        self.assertEqual(duplicates[0]["drop"], [3])

    def test_criteria_differing_only_in_operator_are_not_duplicates(self):
        duplicates = find_duplicate_criteria(
            {
                "crmCriteria": [
                    criterion("a", "Equals", "1"),
                    criterion("a", "NotEqual", "1"),
                ]
            }
        )
        self.assertEqual(duplicates, [])

    def test_canonical_expression_ignores_row_numbering(self):
        rows = [criterion("a"), criterion("b"), criterion("a")]
        deduped = [criterion("a"), criterion("b")]
        self.assertEqual(
            canonical_expression("1 AND (2 OR 3)", rows),
            canonical_expression("1 AND (2 OR 1)", deduped),
        )

    def test_canonical_expression_detects_a_wrong_remap(self):
        rows = [criterion("a"), criterion("b"), criterion("a")]
        deduped = [criterion("a"), criterion("b")]
        self.assertNotEqual(
            canonical_expression("1 AND (2 OR 3)", rows),
            canonical_expression("1 AND (2 OR 2)", deduped),
        )

    def test_null_right_values_compare_as_duplicates(self):
        repair = repair_duplicate_criteria(
            {
                "crmCriteria": [
                    criterion("a", "Equals", None),
                    criterion("a", "Equals", None),
                ],
                "grouping": {"expression": "1 OR 2", "type": "Custom"},
            }
        )
        self.assertEqual(repair["rows_after"], 1)
        self.assertTrue(repair["equivalent"])

    def test_not_operator_is_preserved(self):
        repair = repair_duplicate_criteria(
            {
                "crmCriteria": [criterion("a"), criterion("b"), criterion("a")],
                "grouping": {"expression": "NOT 3 AND (1 OR 2)", "type": "Custom"},
            }
        )
        self.assertEqual(repair["grouping"]["expression"], "NOT 1 AND (1 OR 2)")
        self.assertTrue(repair["equivalent"])


if __name__ == "__main__":
    unittest.main()
