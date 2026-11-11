"""
Unit tests for Registration Manager transliteration and advanced multi-factor deduplication.
Tests Cyrillic-to-Latin conversion, exact and inverted deduplication, cross-script matching,
accent normalization, and output verification.
"""

import re
import unittest
from pathlib import Path

from agents.registration_manager.tools import (
    clean_and_validate_name,
    get_name_dedup_keys,
    normalize_name_token,
    process_registrations,
    stage_manual_text_registrations,
    transliterate_cyrillic_to_latin,
    verify_and_deduplicate_registrations,
)


class TestRegistrationTransliteration(unittest.TestCase):
    """Verifies that Cyrillic text is accurately transliterated into Latin script across all Slavic languages."""

    def test_transliterate_empty_and_latin(self):
        self.assertEqual(transliterate_cyrillic_to_latin(""), "")
        self.assertEqual(transliterate_cyrillic_to_latin("John Doe"), "John Doe")
        self.assertEqual(transliterate_cyrillic_to_latin("Michał Kowalski"), "Michał Kowalski")

    def test_transliterate_russian_names(self):
        self.assertEqual(transliterate_cyrillic_to_latin("Александр"), "Aleksandr")
        self.assertEqual(transliterate_cyrillic_to_latin("Оплачиков"), "Oplachikov")
        self.assertEqual(transliterate_cyrillic_to_latin("Юлия Оплачикова"), "Yuliya Oplachikova")
        self.assertEqual(transliterate_cyrillic_to_latin("Дмитрий"), "Dmitriy")
        self.assertEqual(transliterate_cyrillic_to_latin("Щербаков"), "Shcherbakov")

    def test_transliterate_ukrainian_and_belarusian_names(self):
        # Ukrainian apostrophes and special characters
        self.assertEqual(transliterate_cyrillic_to_latin("Мар'яна"), "Maryana")
        self.assertEqual(transliterate_cyrillic_to_latin("В’ячеслав"), "Vyacheslav")
        self.assertEqual(transliterate_cyrillic_to_latin("Євгеній Цвєтков"), "Yevgeniy Tsvyetkov")
        # Belarusian specific
        self.assertEqual(transliterate_cyrillic_to_latin("Арына Сцяпанава"), "Aryna Stsyapanava")
        self.assertEqual(transliterate_cyrillic_to_latin("Ўладзімір"), "Uladzimir")

    def test_transliterate_preserves_uppercase_and_titlecase(self):
        self.assertEqual(transliterate_cyrillic_to_latin("ИВАН ИВАНОВ"), "IVAN IVANOV")
        self.assertEqual(transliterate_cyrillic_to_latin("Иван Иванов"), "Ivan Ivanov")

    def test_clean_and_validate_name_transliterates_cyrillic(self):
        fn, ln, err = clean_and_validate_name("Александр", "Оплачиков")
        self.assertEqual(err, "")
        self.assertEqual(fn, "Aleksandr")
        self.assertEqual(ln, "Oplachikov")
        # Ensure no Cyrillic remains
        self.assertFalse(any("\u0400" <= c <= "\u04ff" for c in f"{fn} {ln}"))


class TestRegistrationDeduplication(unittest.TestCase):
    """Verifies that multi-factor deduplication catches direct, inverted, cross-script, and accented duplicates."""

    def test_normalize_token_strips_accents_and_transliterates(self):
        self.assertEqual(normalize_name_token("Michał"), "michal")
        self.assertEqual(normalize_name_token("Michal"), "michal")
        self.assertEqual(normalize_name_token("Gültaç"), "gultac")
        self.assertEqual(normalize_name_token("Иван"), "ivan")

    def test_get_name_dedup_keys_inverted_and_token_sets(self):
        dir1, inv1, tok1 = get_name_dedup_keys("Ivan", "Ivanov")
        dir2, inv2, tok2 = get_name_dedup_keys("Ivanov", "Ivan")
        self.assertEqual(dir1, inv2)
        self.assertEqual(inv1, dir2)
        self.assertEqual(tok1, tok2)

    def test_verify_and_deduplicate_tool_detects_all_duplicate_variants(self):
        sample_list = (
            "Ivan Ivanov\n"
            "Иван Иванов\n"  # Cross-script duplicate
            "Ivanov Ivan\n"  # Inverted duplicate
            "Michał Kowalski\n"
            "Michal Kowalski\n"  # Accent variation duplicate
            "Anna Nowak\n"
            "John Doe\n"
        )
        report = verify_and_deduplicate_registrations(text_content=sample_list)
        self.assertIn("Attendee List Verification & Deduplication Audit", report)
        self.assertIn("Total Records Scanned**: 7", report)
        self.assertIn("Unique Valid Attendees**: **4**", report)
        self.assertIn("Total Duplicates Identified & Filtered**: **3**", report)
        self.assertIn("Cross-Script Matches", report)
        self.assertIn("Inverted Names", report)
        self.assertIn("Diacritic / Accent Variations", report)


class TestProcessRegistrationsEndToEnd(unittest.TestCase):
    """Verifies end-to-end processing guarantees zero Cyrillic in deliverables and zero duplicates."""

    def test_process_registrations_eliminates_duplicates_and_cyrillic(self):
        raw_attendees = (
            "Full Name\n"
            "Александр Оплачиков\n"
            "Aleksandr Oplachikov\n"  # Cross-script duplicate of above
            "Oplachikov Aleksandr\n"  # Inverted duplicate
            "Юлия Оплачикова\n"
            "Yuliya Oplachikova\n"  # Duplicate
            "Piotr Wiśniewski\n"
            "Piotr Wisniewski\n"  # Accent duplicate
            "Wiśniewski Piotr\n"  # Inverted duplicate
            "Jan Kowalski\n"
        )
        staged_path = stage_manual_text_registrations(raw_attendees)
        summary = process_registrations(file_path=staged_path, capacity=10)["result"]

        self.assertIn("Event Registration Processing Summary", summary)
        self.assertIn("Script Normalization", summary)

        # Verify plain-text roster file
        results_dir = Path(__file__).parent.parent / "agents" / "registration_manager" / "results"
        txt_path = results_dir / "registrations_list.txt"
        self.assertTrue(txt_path.exists())

        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check there is ABSOLUTELY NO CYRILLIC in the roster file
        cyrillic_matches = [c for c in content if "\u0400" <= c <= "\u04ff"]
        self.assertEqual(
            cyrillic_matches,
            [],
            f"Expected no Cyrillic in output roster, found: {cyrillic_matches}",
        )

        # Check that unique attendees count is exact:
        # Aleksandr Oplachikov, Yuliya Oplachikova, Piotr Wisniewski, Jan Kowalski -> exactly 4 unique!
        confirmed_match = re.search(r"Confirmed Attendees \((\d+)\)", content)
        self.assertIsNotNone(confirmed_match)
        confirmed_count = int(confirmed_match.group(1))
        self.assertEqual(confirmed_count, 4)

    def test_verify_with_manual_priority_additions(self):
        sample_list = "John Doe\nJane Smith\nBob Wilson\n"
        manual_list = "VIP Guest, Jane Smith"
        report = verify_and_deduplicate_registrations(text_content=sample_list, manual_confirmed=manual_list)

        self.assertIn("Attendee List Verification & Deduplication Audit", report)
        self.assertIn("Manual Priority Inclusions**: **2**", report)
        self.assertIn("(Manual)", report)
        # Jane Smith was duplicated in the standard list and merged into manual priority
        self.assertIn("Manual Priority Matches*: 1", report)

    def test_process_registrations_with_manual_priority_and_alignment(self):
        # 12 attendees to test 1-digit and 2-digit number padding/alignment
        attendee_lines = ["Full Name"] + [f"Attendee Person{i}" for i in range(1, 13)]
        raw_csv = "\n".join(attendee_lines)
        staged_path = stage_manual_text_registrations(raw_csv)
        summary = process_registrations(
            file_path=staged_path,
            capacity=10,
            manual_confirmed="Priority VIP Person, Special Guest",
        )["result"]

        self.assertIn("Manual Priority Additions*: 2", summary)

        results_dir = Path(__file__).parent.parent / "agents" / "registration_manager" / "results"
        txt_path = results_dir / "registrations_list.txt"
        self.assertTrue(txt_path.exists())

        with open(txt_path, "r", encoding="utf-8") as f:
            lines = [line for line in f.read().split("\n") if line.strip()]

        # Check that (Manual) tag is applied
        manual_lines = [line for line in lines if "(Manual)" in line]
        self.assertGreaterEqual(len(manual_lines), 2)

        # Check right-aligned number formatting:
        # For a list with >= 10 items, item 1 should be ' 1.' and item 10 should be '10.'
        item_1_line = next(line for line in lines if " 1." in line)
        item_10_line = next(line for line in lines if "10." in line)
        self.assertTrue(item_1_line.startswith(" 1."))
        self.assertTrue(item_10_line.startswith("10."))


if __name__ == "__main__":
    unittest.main()
