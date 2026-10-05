import asyncio
import unittest

from hyro.providers import PROVIDERS, normalize
from hyro.schemas import Requirements
from hyro.scoring import extract_requirements, score


class LogicTests(unittest.TestCase):
    def test_extract_and_score(self):
        requirements = extract_requirements("Python SQL engineer with 4 years experience")
        self.assertEqual(requirements.required_skills, ["Python", "SQL"])
        self.assertEqual(requirements.minimum_years_experience, 4)
        strong = score(requirements, [{"skills": ["Python", "SQL"], "years": 5, "headline": "Python SQL engineer", "resume_text": "Python SQL"}])
        weak = score(requirements, [{"skills": ["Java"], "years": None, "headline": "Java", "resume_text": None}])
        self.assertGreater(strong["match_score"], weak["match_score"])
        self.assertGreater(strong["confidence"], weak["confidence"])
        self.assertEqual(weak["missing_requirements"][:2], ["Python", "SQL"])

    def test_mock_provider_pages_and_normalization(self):
        async def fetch():
            first, cursor = await PROVIDERS["github"].fetch_page("Python", 0, 1)
            second, end = await PROVIDERS["github"].fetch_page("Python", cursor, 1)
            return first, second, end

        first, second, end = asyncio.run(fetch())
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertIsNone(end)
        self.assertEqual(normalize("github", first[0])["name"], "Asha Rao")


if __name__ == "__main__":
    unittest.main()
