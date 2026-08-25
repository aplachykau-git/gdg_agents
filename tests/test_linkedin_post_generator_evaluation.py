import json
import unittest
from pathlib import Path

from agents.linkedin_post_generator.evaluation.evaluator import (
    build_few_shot_judge_prompt,
    evaluate_missing_input_response,
    evaluate_response,
    load_judge_examples,
    parse_speakers,
    parse_variants,
    validate_judge_result,
)

FIELDS = {
    "speaker_name": "Maya Chen",
    "position": "Senior Mobile Developer",
    "company": "Northstar Labs",
    "speaker_bio": "Maya is a mobile engineer.",
    "talk_title": "Scaling Kotlin Apps Across Wear OS and Android Auto",
    "talk_description": "Shared Kotlin domain logic for Android devices.",
    "community_name": "Krakow",
}


def valid_response(title_in_body=False):
    title = FIELDS["talk_title"] if title_in_body else "Cross-device Android architecture"
    return f"""### Variant 1: Architectural Perspective
🚀 @{FIELDS["speaker_name"]}, {FIELDS["position"]} at {FIELDS["company"]}, will unpack {title} through shared Kotlin domain logic.

Join us and secure your spot.

#GDGKrakow #AndroidDev #Kotlin #Architecture
### Variant 2: Engineering Focus
💻 @{FIELDS["speaker_name"]}, {FIELDS["position"]} at {FIELDS["company"]}, will explore modular boundaries for Android experiences beyond one screen.

Register today and save your seat.

#GDGKrakow #AndroidDev #Kotlin #Mobile
### Variant 3: Community Focus
🧠 Meet @{FIELDS["speaker_name"]}, {FIELDS["position"]} at {FIELDS["company"]}, for a practical discussion of reusable domain logic across devices.

Sign up now to reserve your spot.

#GDGKrakow #AndroidDev #Engineering #Community"""


def failures(results):
    return {result.rule_id for result in results if not result.passed}


class LinkedInPostGeneratorEvaluationTests(unittest.TestCase):
    def test_parse_variants_returns_three_bodies(self):
        variants = parse_variants(valid_response())
        self.assertEqual([variant.number for variant in variants], [1, 2, 3])
        self.assertEqual(variants[0].name, "Architectural Perspective")

    def test_complete_response_passes_deterministic_contract(self):
        self.assertFalse(failures(evaluate_response(valid_response(), FIELDS)))

    def test_full_talk_title_in_body_fails(self):
        self.assertIn(
            "talk_title_not_in_body",
            failures(evaluate_response(valid_response(title_in_body=True), FIELDS)),
        )

    def test_missing_input_clarification_cannot_generate_variants(self):
        fields = {key: value for key, value in FIELDS.items() if key != "talk_description"}
        response = "Please provide the talk description before I draft the LinkedIn post."
        self.assertFalse(failures(evaluate_missing_input_response(response, fields)))
        generated = response + "\n\n### Variant 1: Incorrect"
        self.assertIn(
            "no_partial_generation",
            failures(evaluate_missing_input_response(generated, fields)),
        )
        optional_request = response + "\nRegistration link: please provide one."
        self.assertIn(
            "no_optional_field_request",
            failures(evaluate_missing_input_response(optional_request, fields)),
        )

    def test_cta_can_appear_before_the_final_paragraph(self):
        response = valid_response().replace(
            "Join us and secure your spot.\n\n#GDGKrakow",
            "Join us and secure your spot.\n\nLearn more about the session before the meetup.\n\n#GDGKrakow",
        )
        self.assertNotIn("cta", failures(evaluate_response(response, FIELDS)))

    def test_hashtag_footer_does_not_invalidate_cta_or_paragraph_count(self):
        results = evaluate_response(valid_response(), FIELDS)
        failed = failures(results)
        self.assertNotIn("cta", failed)
        self.assertNotIn("narrative_format", failed)

    def test_missing_cta_fails(self):
        response = valid_response().replace("Join us and secure your spot.", "Learn more about the session.")
        self.assertIn("cta", failures(evaluate_response(response, FIELDS)))

    def test_multi_speaker_announcements_accept_three_variants_per_speaker(self):
        request = """Create separate LinkedIn speaker announcements.
Speaker name: Maya Chen
Position: Senior Mobile Developer
Company: Northstar Labs
Speaker bio: Maya is a mobile engineer.
Talk title: Kotlin Architecture
Talk description: Kotlin architecture across devices.
Second speaker name: Omar Ali
Second speaker position: Cloud Engineer
Second speaker company: Atlas Systems
Second speaker bio: Omar is a cloud engineer.
Second speaker talk title: Serverless Observability
Second speaker talk description: Tracing and alerts for serverless APIs."""
        speakers = parse_speakers(request)
        primary = valid_response().replace(
            FIELDS["talk_title"],
            "Kotlin Architecture",
        )
        secondary = (
            valid_response()
            .replace("Maya Chen", "Omar Ali")
            .replace("Senior Mobile Developer", "Cloud Engineer")
            .replace("Northstar Labs", "Atlas Systems")
            .replace(FIELDS["talk_title"], "Serverless Observability")
        )
        response = f"{primary}\n\n{secondary}"
        self.assertNotIn(
            "variant_count_and_headers",
            failures(
                evaluate_response(
                    response,
                    FIELDS,
                    speakers=speakers,
                    request_text=request,
                )
            ),
        )

    def test_judge_result_validation_accepts_contract(self):
        for payload in [
            {"verdict": "unknown", "score": None, "reason": "The description is vague."},
            {"verdict": "pass", "score": 92, "reason": "Supported by the description."},
            {"verdict": "fail", "score": 7, "reason": "Unrelated to the source."},
        ]:
            self.assertEqual(validate_judge_result(payload), payload)

    def test_judge_result_validation_rejects_invalid_contract(self):
        for payload in [
            {"verdict": "unknown", "score": 50, "reason": "Invalid score."},
            {"verdict": "pass", "score": None, "reason": "Missing score."},
            {"verdict": "maybe", "score": 50, "reason": "Bad verdict."},
            {"verdict": "fail", "score": 101, "reason": "Out of range."},
        ]:
            with self.assertRaises(ValueError):
                validate_judge_result(payload)

    def test_few_shot_prompt_uses_train_examples_not_held_out_examples(self):
        train = load_judge_examples("train")
        held_out = load_judge_examples("eval")
        prompt = build_few_shot_judge_prompt(
            "topic_alignment",
            train[0]["source"],
            train[0]["post_body"],
        )
        self.assertIn(
            train[0]["post_body"].replace("\n", "\\n"),
            prompt,
        )
        self.assertNotIn(held_out[0]["post_body"], prompt)

    def test_dataset_sizes_and_disjoint_content(self):
        root = Path(__file__).parent / "eval"
        train = json.loads(
            (root / "../../agents/linkedin_post_generator/evaluation/judge_train.json").resolve().read_text()
        )
        held_out = json.loads(
            (root / "../../agents/linkedin_post_generator/evaluation/judge_eval.json").resolve().read_text()
        )
        self.assertEqual(len(train["examples"]), 6)
        self.assertEqual(len(held_out["examples"]), 6)
        self.assertTrue(
            {item["post_body"] for item in train["examples"]}.isdisjoint(
                {item["post_body"] for item in held_out["examples"]}
            )
        )


if __name__ == "__main__":
    unittest.main()
