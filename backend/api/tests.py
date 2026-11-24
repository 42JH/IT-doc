from datetime import datetime, time
from types import SimpleNamespace

from django.test import SimpleTestCase

from .services import bayesian_rating, haversine_km, is_open_now, normalize


class NormalizeTests(SimpleTestCase):
    def test_removes_whitespace_and_lowercases(self):
        self.assertEqual(normalize("  가슴 통증 "), "가슴통증")
        self.assertEqual(normalize(" Head Ache "), "headache")

    def test_replaces_synonyms_after_removing_spaces(self):
        # 공백을 먼저 지워야 '열이 나고'에도 '열이나'→'발열'이 적용된다.
        self.assertEqual(normalize("열이 나고"), "발열고")
        self.assertEqual(normalize("배가 아파요"), "복통아파요")

    def test_keeps_text_without_synonyms(self):
        self.assertEqual(normalize("두통"), "두통")


class BayesianRatingTests(SimpleTestCase):
    def test_no_reviews_returns_global_mean(self):
        self.assertEqual(bayesian_rating(5.0, 0, 3.5), 3.5)

    def test_few_reviews_pulled_toward_global_mean(self):
        # (5*3.5 + 1*5.0) / (5+1) = 3.75
        self.assertAlmostEqual(bayesian_rating(5.0, 1, 3.5), 3.75)

    def test_many_reviews_beat_single_perfect_review(self):
        self.assertGreater(bayesian_rating(4.3, 200, 3.5), bayesian_rating(5.0, 1, 3.5))

    def test_custom_prior(self):
        self.assertAlmostEqual(bayesian_rating(5.0, 2, 3.0, prior=2), 4.0)


class HaversineTests(SimpleTestCase):
    def test_same_point_is_zero(self):
        self.assertEqual(haversine_km(36.12, 128.34, 36.12, 128.34), 0.0)

    def test_one_degree_latitude(self):
        self.assertAlmostEqual(haversine_km(0, 0, 1, 0), 111.195, places=2)

    def test_seoul_to_busan_and_symmetric(self):
        d = haversine_km(37.5665, 126.9780, 35.1796, 129.0756)
        self.assertAlmostEqual(d, 325.1, delta=0.5)
        self.assertAlmostEqual(d, haversine_km(35.1796, 129.0756, 37.5665, 126.9780))


def hospital(**kwargs):
    fields = dict(
        open_time=time(9), close_time=time(18),
        sat_open_time=None, sat_close_time=None,
        sun_open_time=None, sun_close_time=None,
    )
    fields.update(kwargs)
    return SimpleNamespace(**fields)


# 2026-11-23은 월요일, 11-28은 토요일, 11-29는 일요일.
MON = datetime(2026, 11, 23)
SAT = datetime(2026, 11, 28)
SUN = datetime(2026, 11, 29)


class IsOpenNowTests(SimpleTestCase):
    def test_weekday_hours(self):
        h = hospital()
        self.assertTrue(is_open_now(h, MON.replace(hour=9)))
        self.assertTrue(is_open_now(h, MON.replace(hour=18)))
        self.assertFalse(is_open_now(h, MON.replace(hour=8, minute=59)))
        self.assertFalse(is_open_now(h, MON.replace(hour=18, minute=1)))

    def test_closed_when_weekend_hours_missing(self):
        h = hospital()
        self.assertFalse(is_open_now(h, SAT.replace(hour=10)))
        self.assertFalse(is_open_now(h, SUN.replace(hour=10)))

    def test_weekend_uses_own_fields(self):
        h = hospital(sat_open_time=time(9), sat_close_time=time(13),
                     sun_open_time=time(10), sun_close_time=time(12))
        self.assertTrue(is_open_now(h, SAT.replace(hour=12)))
        self.assertFalse(is_open_now(h, SAT.replace(hour=14)))
        self.assertTrue(is_open_now(h, SUN.replace(hour=11)))
        self.assertFalse(is_open_now(h, SUN.replace(hour=9)))

    def test_past_midnight_hours(self):
        h = hospital(open_time=time(18), close_time=time(2))
        self.assertTrue(is_open_now(h, MON.replace(hour=23)))
        self.assertTrue(is_open_now(h, MON.replace(hour=1, minute=30)))
        self.assertFalse(is_open_now(h, MON.replace(hour=12)))
