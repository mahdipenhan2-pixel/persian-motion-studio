#!/usr/bin/env python3
"""Offline unit tests for Stage 2 Persian token alignment (no API/audio required)."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("story_stage2", ROOT / "scripts" / "story_stage2.py")
STAGE2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE2)


def whisper(tokens, step=0.4):
    return [
        {"text": token, "norm": STAGE2.norm(token),
         "start": i * step, "end": i * step + 0.32}
        for i, token in enumerate(tokens)
    ]


class PersianAlignmentTests(unittest.TestCase):
    def align(self, script, recognized):
        return STAGE2.align_words(STAGE2.script_tokens(script), whisper(recognized), 0.6)

    def test_exact_words(self):
        rows, ratio = self.align("سلام دنیا", ["سلام", "دنیا"])
        self.assertEqual(ratio, 1.0)
        self.assertEqual([r["status"] for r in rows], ["exact", "exact"])

    def test_one_script_word_split_by_whisper(self):
        rows, ratio = self.align("پایتخت افغانستان", ["پای", "تخت", "افغانستان"])
        self.assertEqual(ratio, 1.0)
        self.assertEqual(rows[0]["recognized"], ["پای", "تخت"])
        self.assertEqual(rows[0]["status"], "aligned")
        self.assertEqual(rows[0]["timing_quality"], "estimated")
        self.assertLess(rows[0]["start"], rows[0]["end"])

    def test_two_script_words_merged_by_whisper(self):
        rows, ratio = self.align("این کشور", ["اینکشور"])
        self.assertEqual(ratio, 1.0)
        self.assertEqual([r["status"] for r in rows], ["aligned", "aligned"])
        self.assertTrue(all(r["timing_quality"] == "estimated" for r in rows))
        self.assertLessEqual(rows[0]["end"], rows[1]["start"] + 0.001)

    def test_missing_script_word_is_not_given_fake_time(self):
        rows, ratio = self.align(
            "این کشور با شش کشور همسایه مرز مشترک دارد",
            ["این", "کشور", "با", "کشور", "همسایه", "مرز", "مشترک", "دارد"],
        )
        missing = next(r for r in rows if r["text"] == "شش")
        self.assertEqual(missing["status"], "unmatched")
        self.assertEqual(missing["timing_quality"], "unresolved")
        self.assertIsNone(missing["start"])
        self.assertGreaterEqual(ratio, 0.85)

    def test_minor_persian_asr_spelling_difference(self):
        rows, ratio = self.align("قندهار در جنوب", ["قندحار", "در", "جنوب"])
        self.assertEqual(ratio, 1.0)
        self.assertEqual(rows[0]["status"], "aligned")
        self.assertEqual(rows[0]["recognized"], ["قندحار"])


    def test_afghanistan_six_sentence_regression(self):
        cases = [
            ("افغانستان کشوری در قلب آسیا است", ["افغانستان", "کشوری", "در", "قلب", "آسی", "است"]),
            ("این کشور با شش کشور همسایه مرز مشترک دارد",
             ["این", "کشور", "با", "کشور", "همسایه", "مرز", "مشترک", "دارد"]),
            ("پایتخت افغانستان کابل است و در میان کوه‌های هندوکش قرار دارد",
             ["پای", "تخت", "افغانستان", "کابولست", "و", "در", "میان", "کو", "های", "هندوکش", "قرار", "دارد"]),
            ("هرات در غرب قندهار در جنوب و مزار شریف در شمال کشور قرار دارند",
             ["هرات", "در", "غرب", "قندحار", "در", "جنوب", "و", "مزار", "شریف", "در", "شمال", "کشفر", "قرار", "دارند"]),
            ("این کشور هیچ مرز دریایی ندارد و در خشکی محصور است",
             ["این", "کشفر", "هیچ", "مرز", "دریایی", "ندارد", "و", "در", "خوشگی", "محسور", "است"]),
            ("کوهستان‌ها و تاریخ کهن به این سرزمین هویت ویژه‌ای داده‌اند",
             ["کوهستانها", "و", "تاریخ", "که", "هن", "به", "این", "سر", "زمین", "هویت", "ویژه‌ای", "داده‌اند"]),
        ]
        results = []
        for script, recognized in cases:
            rows, ratio = STAGE2.align_words(STAGE2.script_tokens(script), whisper(recognized), 0.6)
            results.append((rows, ratio))
        # Only the deliberately omitted word "شش" should remain unresolved.
        unresolved = [r["text"] for rows, _ in results for r in rows if r["status"] == "unmatched"]
        self.assertEqual(unresolved, ["شش"])
        self.assertEqual(results[1][1], 8 / 9)
        self.assertTrue(all(r["timing_quality"] in ("exact", "estimated", "unresolved", "none")
                            for rows, _ in results for r in rows))

    def test_persian_unicode_normalization(self):
        self.assertEqual(STAGE2.norm("كشور ي"), STAGE2.norm("کشور ی"))
        self.assertEqual(STAGE2.norm("کوه‌های"), STAGE2.norm("کوه های"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
