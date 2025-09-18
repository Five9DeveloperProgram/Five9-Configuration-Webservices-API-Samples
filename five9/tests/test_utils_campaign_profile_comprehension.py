import unittest
from five9.utils.campaign_profile_comprehension import prettify, demystify_filter, remystify_filter, remystify_filter_in_place


class TestCampaignProfileComprehension(unittest.TestCase):
    def setUp(self):
        self.sample_profile_filter = {
            'grouping': {'expression': '1 AND (2 OR 3)', 'type': 'Custom'},
            'crmCriteria': [
                {'leftValue': 'fieldA', 'compareOperator': 'Equals', 'rightValue': 'abc'},
                {'leftValue': 'fieldB', 'compareOperator': 'Greater', 'rightValue': '10'},
                {'leftValue': 'fieldC', 'compareOperator': 'Less', 'rightValue': '20'},
            ]
        }

    def test_prettify(self):
        ugly = '(A(B(C)))'
        pretty = prettify(ugly, '(', ')')
        self.assertIn('\n', pretty)

    def test_demystify_filter(self):
        result = demystify_filter(self.sample_profile_filter)
        self.assertIn('fieldA', result)
        self.assertIn('fieldB', result)
        self.assertIn('fieldC', result)

    def test_remystify_filter_round_trip(self):
        demystified = demystify_filter(self.sample_profile_filter)
        remystified = remystify_filter(demystified)
        self.assertEqual(len(remystified['crmCriteria']), 3)
        self.assertEqual(remystified['grouping']['type'], 'Custom')

    def test_remystify_filter_in_place(self):
        test_string = '[fieldA ::Equals:: 1][1] AND [fieldB ::Greater:: 2][2]'
        result = remystify_filter_in_place(test_string)
        self.assertNotIn('[fieldA', result)


if __name__ == '__main__':
    unittest.main()
