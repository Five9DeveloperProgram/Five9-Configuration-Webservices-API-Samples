import unittest
from datetime import date
from unittest.mock import Mock, call

from examples.domain_config.create_devry_campaign_profiles import (
    DEFAULT_PROFILE_NAME,
    criteria_for_write,
    create_profile,
    load_definitions,
    replace_filter,
    update_profile_description,
)


class TestCreateDevryCampaignProfiles(unittest.TestCase):
    def setUp(self):
        self.profile_filter = {
            "crmCriteria": [
                {
                    "leftValue": "fieldA",
                    "compareOperator": "Equals",
                    "rightValue": "one",
                }
            ],
            "grouping": {"expression": "1", "type": "Custom"},
            "orderByFields": [],
        }

    def test_default_definition_loads(self):
        definitions = load_definitions(DEFAULT_PROFILE_NAME)
        self.assertEqual(list(definitions), [DEFAULT_PROFILE_NAME])
        self.assertGreater(len(definitions[DEFAULT_PROFILE_NAME]["crmCriteria"]), 0)

    def test_vertical_dialer_definitions_load(self):
        definitions = load_definitions(definitions_dir="scratch/oDEM Vertical Dialers")
        self.assertEqual(len(definitions), 97)
        self.assertIn("oDEM Other Green Aged Weekday", definitions)

    def test_criteria_for_write_emits_empty_null_values_without_mutating_source(self):
        criteria = [
            {
                "leftValue": "fieldA",
                "compareOperator": "Equals",
                "rightValue": None,
            }
        ]

        writable = criteria_for_write(criteria)

        self.assertIsNone(criteria[0]["rightValue"])
        self.assertEqual(writable[0]["rightValue"], "")

    def test_create_profile_clones_base_and_verifies_filter(self):
        client = Mock()
        client.throttled_service.getCampaignProfileFilter.return_value = (
            self.profile_filter
        )
        base_profile = {"name": "base", "description": "copied"}

        create_profile(
            client,
            base_profile,
            "new profile",
            self.profile_filter,
            created_on=date(2026, 9, 11),
        )

        self.assertEqual(base_profile["name"], "base")
        self.assertEqual(
            client.throttled_service.method_calls,
            [
                call.createCampaignProfile(
                    campaignProfile={
                        "name": "new profile",
                        "description": (
                            "Generated from custom expression processor - 2026-09-11"
                        ),
                    }
                ),
                call.modifyCampaignProfileCrmCriteria(
                    profileName="new profile",
                    grouping={"expression": "1", "type": "Custom"},
                    addCriteria=self.profile_filter["crmCriteria"],
                ),
                call.getCampaignProfileFilter(profileName="new profile"),
            ],
        )

    def test_create_profile_raises_when_read_back_differs(self):
        client = Mock()
        client.throttled_service.getCampaignProfileFilter.return_value = {
            "crmCriteria": [],
            "grouping": {"expression": "", "type": "All"},
        }

        with self.assertRaisesRegex(RuntimeError, "verification failed"):
            create_profile(client, {"name": "base"}, "new profile", self.profile_filter)

    def test_update_profile_description_preserves_source_profile(self):
        client = Mock()
        profile = {"name": "existing", "description": "old", "enabled": True}

        update_profile_description(client, profile, created_on=date(2026, 9, 11))

        self.assertEqual(profile["description"], "old")
        client.throttled_service.modifyCampaignProfile.assert_called_once_with(
            {
                "name": "existing",
                "description": (
                    "Generated from custom expression processor - 2026-09-11"
                ),
                "enabled": True,
            }
        )

    def test_apply_filter_rejects_a_nonmatching_existing_prefix(self):
        from examples.domain_config.create_devry_campaign_profiles import apply_filter

        client = Mock()
        existing = [
            {
                "leftValue": "differentField",
                "compareOperator": "Equals",
                "rightValue": "one",
            }
        ]

        with self.assertRaisesRegex(ValueError, "expected filter prefix"):
            apply_filter(client, "new profile", self.profile_filter, existing)
        client.throttled_service.assert_not_called()

    def test_apply_filter_atomically_replaces_an_existing_prefix(self):
        from examples.domain_config.create_devry_campaign_profiles import apply_filter

        client = Mock()
        client.throttled_service.getCampaignProfileFilter.return_value = (
            self.profile_filter
        )
        existing = [self.profile_filter["crmCriteria"][0]]

        apply_filter(client, "new profile", self.profile_filter, existing)

        client.throttled_service.modifyCampaignProfileCrmCriteria.assert_called_once_with(
            profileName="new profile",
            grouping=self.profile_filter["grouping"],
            addCriteria=self.profile_filter["crmCriteria"],
            removeCriteria=existing,
        )

    def test_replace_filter_accepts_differing_existing_criteria(self):
        client = Mock()
        client.throttled_service.getCampaignProfileFilter.return_value = (
            self.profile_filter
        )
        existing = [
            {
                "leftValue": "oldField",
                "compareOperator": "Equals",
                "rightValue": "old",
            }
        ]

        replace_filter(client, "existing profile", self.profile_filter, existing)

        client.throttled_service.modifyCampaignProfileCrmCriteria.assert_called_once_with(
            profileName="existing profile",
            grouping=self.profile_filter["grouping"],
            addCriteria=self.profile_filter["crmCriteria"],
            removeCriteria=existing,
        )


if __name__ == "__main__":
    unittest.main()
