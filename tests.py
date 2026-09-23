"""Unit tests. Run with: python3 tests.py"""

import unittest

import analysis
from analysis import (
    SessionAnalyzer,
    average,
    minimum_and_maximum,
    percentage,
    split_half_difference,
    summarise,
)
from models import Observation, Participant, Session
from reporting import DetailedSessionReport, SessionReport, format_value
from sample_data import build_all_sessions, build_session_from_generator
from validation import (
    ImpossibleValueRule,
    MissingValueRule,
    ObservationValidator,
    OrderedTimestampRule,
    SignalQualityRule,
)


def make_observation(**overrides):
    """A valid observation, with any field overridden for a specific test."""
    fields = {
        "timestamp": 0,
        "heart_rate": 110,
        "skin_response": 2.0,
        "temperature": 33.0,
        "activity_level": 0.5,
        "signal_quality": 0.9,
    }
    fields.update(overrides)
    return Observation(**fields)


def make_participant():
    return Participant("P001", 70, 1.8, 32.5)


class TestParticipant(unittest.TestCase):

    def test_from_profile_builds_participant(self):
        profile = {
            "participant_id": "P042",
            "baseline_heart_rate": 65,
            "baseline_skin_response": 1.5,
            "baseline_temperature": 32.0,
        }
        participant = Participant.from_profile(profile)
        self.assertEqual(participant.participant_id, "P042")
        self.assertEqual(participant.baseline_heart_rate, 65.0)

    def test_from_profile_rejects_incomplete_dictionary(self):
        with self.assertRaises(KeyError):
            Participant.from_profile({"participant_id": "P001"})

    def test_baseline_is_read_only(self):
        participant = make_participant()
        with self.assertRaises(AttributeError):
            participant.baseline_heart_rate = 200

    def test_empty_identifier_is_rejected(self):
        with self.assertRaises(ValueError):
            Participant("   ", 70, 1.8, 32.5)

    def test_comparison_against_baseline(self):
        participant = make_participant()
        self.assertEqual(participant.heart_rate_above_baseline(100), 30.0)


class TestObservation(unittest.TestCase):

    def test_missing_keys_become_none(self):
        observation = Observation.from_dict({"timestamp": 3})
        self.assertEqual(observation.timestamp, 3)
        self.assertIsNone(observation.heart_rate)

    def test_unvalidated_observation_is_not_usable(self):
        observation = make_observation()
        self.assertFalse(observation.is_validated)
        self.assertFalse(observation.is_usable)

    def test_recording_no_problems_marks_it_usable(self):
        observation = make_observation()
        observation.record_validation([])
        self.assertTrue(observation.is_usable)

    def test_problems_list_cannot_be_edited_from_outside(self):
        observation = make_observation()
        observation.record_validation(["a problem"])
        observation.problems.append("injected")
        self.assertEqual(len(observation.problems), 1)


class TestSession(unittest.TestCase):

    def test_rejects_wrong_participant_type(self):
        with self.assertRaises(TypeError):
            Session("not a participant", [])

    def test_rejects_wrong_observation_type(self):
        with self.assertRaises(TypeError):
            Session(make_participant(), [{"timestamp": 0}])

    def test_observation_list_is_a_copy(self):
        session = Session(make_participant(), [make_observation()])
        session.observations.append(make_observation())
        self.assertEqual(session.total_count, 1)


class TestValidationRules(unittest.TestCase):

    def test_missing_value_is_caught(self):
        problems = MissingValueRule().check(make_observation(heart_rate=None))
        self.assertEqual(len(problems), 1)

    def test_boolean_is_not_accepted_as_a_number(self):
        problems = MissingValueRule().check(make_observation(heart_rate=True))
        self.assertEqual(len(problems), 1)

    def test_impossible_heart_rate_is_caught(self):
        problems = ImpossibleValueRule().check(make_observation(heart_rate=265))
        self.assertEqual(len(problems), 1)

    def test_negative_activity_is_caught(self):
        problems = ImpossibleValueRule().check(make_observation(activity_level=-0.2))
        self.assertEqual(len(problems), 1)

    def test_missing_value_is_not_reported_twice(self):
        problems = ImpossibleValueRule().check(make_observation(heart_rate=None))
        self.assertEqual(problems, [])

    def test_low_signal_quality_is_caught(self):
        problems = SignalQualityRule().check(make_observation(signal_quality=0.3))
        self.assertEqual(len(problems), 1)

    def test_good_signal_quality_passes(self):
        self.assertEqual(SignalQualityRule().check(make_observation()), [])

    def test_negative_timestamp_is_caught(self):
        problems = OrderedTimestampRule().check(make_observation(timestamp=-1))
        self.assertEqual(len(problems), 1)

    def test_base_rule_must_be_overridden(self):
        from validation import ValidationRule
        with self.assertRaises(NotImplementedError):
            ValidationRule("base").check(make_observation())


class TestValidator(unittest.TestCase):

    def test_clean_session_passes_every_window(self):
        session = build_session_from_generator("t", "moderate_activity", 42, 12)
        summary = ObservationValidator().validate_session(session)
        self.assertEqual(summary["usable_windows"], 12)
        self.assertEqual(summary["problem_counts"], {})

    def test_poor_quality_session_is_rejected(self):
        session = build_session_from_generator("t", "poor_quality", 42, 12)
        summary = ObservationValidator().validate_session(session)
        self.assertEqual(summary["usable_windows"], 0)

    def test_empty_session_does_not_divide_by_zero(self):
        session = Session(make_participant(), [], label="empty")
        summary = ObservationValidator().validate_session(session)
        self.assertEqual(summary["usable_ratio"], 0.0)


class TestStandaloneFunctions(unittest.TestCase):

    def test_average_of_empty_list_is_none(self):
        self.assertIsNone(average([]))

    def test_average_rounds_to_two_places(self):
        self.assertEqual(average([1, 2, 2]), 1.67)

    def test_minimum_and_maximum(self):
        self.assertEqual(minimum_and_maximum([4, 1, 9]), (1, 9))

    def test_minimum_and_maximum_of_empty_list(self):
        self.assertEqual(minimum_and_maximum([]), (None, None))

    def test_summarise_reports_count(self):
        self.assertEqual(summarise([1, 2, 3])["count"], 3)

    def test_split_half_difference_detects_decline(self):
        self.assertEqual(split_half_difference([10, 10, 2, 2]), 8.0)

    def test_split_half_difference_needs_enough_values(self):
        self.assertIsNone(split_half_difference([1, 2, 3]))

    def test_percentage_handles_zero_total(self):
        self.assertEqual(percentage(3, 0), 0.0)

    def test_format_value_handles_none(self):
        self.assertEqual(format_value(None), "n/a")


class TestClassification(unittest.TestCase):
    """Each generator scenario should produce the matching classification."""

    def setUp(self):
        self.analyzer = SessionAnalyzer()

    def classify(self, scenario, seed=42, windows=12):
        session = build_session_from_generator("t", scenario, seed, windows)
        return self.analyzer.analyze(session)["classification"]

    def test_resting(self):
        self.assertEqual(self.classify("resting"), analysis.RESTING)

    def test_moderate(self):
        self.assertEqual(self.classify("moderate_activity"), analysis.MODERATE)

    def test_high(self):
        self.assertEqual(self.classify("high_activity"), analysis.HIGH)

    def test_recovery(self):
        self.assertEqual(self.classify("recovery"), analysis.RECOVERING)

    def test_poor_quality(self):
        self.assertEqual(self.classify("poor_quality"), analysis.INSUFFICIENT)

    def test_classification_is_stable_across_seeds(self):
        expected = {
            "resting": analysis.RESTING,
            "moderate_activity": analysis.MODERATE,
            "high_activity": analysis.HIGH,
            "recovery": analysis.RECOVERING,
            "poor_quality": analysis.INSUFFICIENT,
        }
        for scenario, want in expected.items():
            for seed in range(1, 21):
                got = self.classify(scenario, seed=seed)
                self.assertEqual(got, want, "{0} seed {1}".format(scenario, seed))

    def test_single_window_is_insufficient(self):
        session = Session(make_participant(), [make_observation()], label="one")
        result = SessionAnalyzer().analyze(session)
        self.assertEqual(result["classification"], analysis.INSUFFICIENT)

    def test_empty_session_is_insufficient(self):
        session = Session(make_participant(), [], label="empty")
        result = SessionAnalyzer().analyze(session)
        self.assertEqual(result["classification"], analysis.INSUFFICIENT)

    def test_result_is_a_dictionary_with_expected_keys(self):
        result = SessionAnalyzer().analyze(
            build_session_from_generator("t", "resting", 42, 12))
        for key in ("classification", "quality", "measurements", "comparison",
                    "trend", "reasons"):
            self.assertIn(key, result)

    def test_every_classification_has_a_reason(self):
        for session in build_all_sessions():
            result = SessionAnalyzer().analyze(session)
            self.assertTrue(result["reasons"], session.label)


class TestReporting(unittest.TestCase):

    def setUp(self):
        session = build_session_from_generator("t", "poor_quality", 42, 12)
        self.result = SessionAnalyzer().analyze(session)

    def test_standard_report_names_the_classification(self):
        text = SessionReport(self.result).render()
        self.assertIn("INSUFFICIENT DATA", text)

    def test_detailed_report_adds_rejected_windows(self):
        standard = SessionReport(self.result).render()
        detailed = DetailedSessionReport(self.result).render()
        self.assertNotIn("Rejected windows", standard)
        self.assertIn("Rejected windows", detailed)

    def test_detailed_report_overrides_the_title(self):
        self.assertIn("[detailed]", DetailedSessionReport(self.result).title())

    def test_report_handles_a_session_with_no_usable_windows(self):
        text = SessionReport(self.result).render()
        self.assertIn("no usable windows", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
