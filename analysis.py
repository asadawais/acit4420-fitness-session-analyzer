"""Summary statistics, recovery detection and session classification.

The constants below are taken from the ranges reported by calibration.py.
"""

import statistics

from validation import ObservationValidator


# A session needs enough usable windows to be summarised at all, and enough of
# the original windows must have survived for the summary to be representative.
MINIMUM_USABLE_WINDOWS = 4
MINIMUM_USABLE_RATIO = 0.5

# Heart rate above the participant's own baseline, in beats per minute.
# Measured means: resting 0.8 to 3.2, moderate 25.7 to 30.2, high 54.5 to 61.4.
RESTING_CEILING = 12.0
MODERATE_CEILING = 45.0

# A recovering session declines from start to finish. Steady sessions drop at
# most 10.5 bpm and 0.100 activity by chance, recovering ones drop at least
# 24.2 bpm and 0.347. Both conditions must hold, since either alone is noisier.
RECOVERY_HEART_RATE_DROP = 15.0
RECOVERY_ACTIVITY_DROP = 0.25

RESTING = "resting"
MODERATE = "moderate activity"
HIGH = "high activity"
RECOVERING = "recovering"
INSUFFICIENT = "insufficient data"


def average(values):
    """Mean of a list of numbers, or None when the list is empty."""
    if not values:
        return None
    return round(statistics.mean(values), 2)


def minimum_and_maximum(values):
    """Smallest and largest value, or (None, None) when the list is empty."""
    if not values:
        return (None, None)
    return (min(values), max(values))


def summarise(values):
    """Average, minimum, maximum and count for one measurement field."""
    lowest, highest = minimum_and_maximum(values)
    return {
        "average": average(values),
        "minimum": lowest,
        "maximum": highest,
        "count": len(values),
    }


def split_half_difference(values):
    """First half mean minus last half mean. Positive means it declined.

    Returns None when there are too few values to split meaningfully.
    """
    if len(values) < 4:
        return None
    half = len(values) // 2
    early = statistics.mean(values[:half])
    late = statistics.mean(values[-half:])
    return round(early - late, 3)


def percentage(part, whole):
    """Part of whole as a percentage, rounded to one decimal."""
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 1)


class SessionAnalyzer:
    """Validates a session, summarises it and classifies its intensity."""

    def __init__(self, validator=None):
        self.validator = validator or ObservationValidator()

    def analyze(self, session):
        """Return a structured dictionary describing one session."""
        quality = self.validator.validate_session(session)
        usable = session.usable_observations()
        participant = session.participant

        heart_rates = [o.heart_rate for o in usable]
        activity_levels = [o.activity_level for o in usable]
        temperatures = [o.temperature for o in usable]
        skin_responses = [o.skin_response for o in usable]

        measurements = {
            "heart_rate": summarise(heart_rates),
            "activity_level": summarise(activity_levels),
            "temperature": summarise(temperatures),
            "skin_response": summarise(skin_responses),
        }

        comparison = self._compare_with_baseline(participant, measurements)
        trend = self._describe_trend(heart_rates, activity_levels)
        classification, reasons = self._classify(quality, comparison, trend)

        return {
            "label": session.label,
            "participant_id": participant.participant_id,
            "baselines": {
                "heart_rate": participant.baseline_heart_rate,
                "skin_response": participant.baseline_skin_response,
                "temperature": participant.baseline_temperature,
            },
            "quality": quality,
            "measurements": measurements,
            "comparison": comparison,
            "trend": trend,
            "classification": classification,
            "reasons": reasons,
            "rejected_detail": [
                {"timestamp": o.timestamp, "problems": o.problems}
                for o in session.rejected_observations()
            ],
        }

    def _compare_with_baseline(self, participant, measurements):
        """How far the session sat above the participant's own references."""
        def difference(method, value):
            if value is None:
                return None
            return round(method(value), 2)

        return {
            "heart_rate_above_baseline": difference(
                participant.heart_rate_above_baseline,
                measurements["heart_rate"]["average"],
            ),
            "temperature_above_baseline": difference(
                participant.temperature_above_baseline,
                measurements["temperature"]["average"],
            ),
            "skin_response_above_baseline": difference(
                participant.skin_response_above_baseline,
                measurements["skin_response"]["average"],
            ),
        }

    def _describe_trend(self, heart_rates, activity_levels):
        """Decline in heart rate and activity between the halves of a session."""
        heart_rate_drop = split_half_difference(heart_rates)
        activity_drop = split_half_difference(activity_levels)

        declining = (
            heart_rate_drop is not None
            and activity_drop is not None
            and heart_rate_drop >= RECOVERY_HEART_RATE_DROP
            and activity_drop >= RECOVERY_ACTIVITY_DROP
        )

        return {
            "heart_rate_drop": heart_rate_drop,
            "activity_drop": activity_drop,
            "is_declining": declining,
        }

    def _classify(self, quality, comparison, trend):
        """Decide the session type and explain the decision.

        Order matters. Recovering sessions average between moderate and high,
        so checking intensity first would hide them.
        """
        reasons = []

        usable = quality["usable_windows"]
        if usable < MINIMUM_USABLE_WINDOWS:
            reasons.append(
                "only {0} of {1} windows were usable, at least {2} are needed".format(
                    usable, quality["total_windows"], MINIMUM_USABLE_WINDOWS
                )
            )
            return INSUFFICIENT, reasons

        if quality["usable_ratio"] < MINIMUM_USABLE_RATIO:
            reasons.append(
                "only {0}% of windows survived validation".format(
                    percentage(usable, quality["total_windows"])
                )
            )
            return INSUFFICIENT, reasons

        elevation = comparison["heart_rate_above_baseline"]
        if elevation is None:
            reasons.append("no usable heart rate measurements")
            return INSUFFICIENT, reasons

        if trend["is_declining"]:
            reasons.append(
                "heart rate fell {0} bpm and activity fell {1} from the first "
                "half to the last".format(
                    trend["heart_rate_drop"], trend["activity_drop"]
                )
            )
            return RECOVERING, reasons

        reasons.append(
            "heart rate averaged {0} bpm above the personal baseline".format(elevation)
        )
        drop = trend["heart_rate_drop"]
        if drop is not None:
            direction = "fell {0}".format(drop) if drop >= 0 else "rose {0}".format(-drop)
            reasons.append(
                "no sustained decline, heart rate {0} bpm between the first "
                "half and the last".format(direction)
            )

        if elevation < RESTING_CEILING:
            return RESTING, reasons
        if elevation < MODERATE_CEILING:
            return MODERATE, reasons
        return HIGH, reasons
