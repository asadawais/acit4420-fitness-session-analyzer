"""Validation rules for individual observation windows.

Each rule returns a list of problem strings. An empty list means the window
passed that rule.
"""


# Clean scenarios sit between 0.82 and 0.99, poor-quality between 0.05 and
# 0.55, so 0.60 separates them with margin on both sides.
MINIMUM_SIGNAL_QUALITY = 0.60

# Ranges follow DATA_DESCRIPTION.md.
HEART_RATE_RANGE = (35, 205)
TEMPERATURE_RANGE = (25.0, 42.0)
ACTIVITY_LEVEL_RANGE = (0.0, 1.0)
SIGNAL_QUALITY_RANGE = (0.0, 1.0)
SKIN_RESPONSE_MINIMUM = 0.0


class ValidationRule:
    """Base class for validation rules. Subclasses override check."""

    def __init__(self, name):
        self.name = name

    def check(self, observation):
        raise NotImplementedError("each rule must implement check")

    def describe(self):
        return self.name

    def __repr__(self):
        return "{0}(name={1!r})".format(type(self).__name__, self.name)


class MissingValueRule(ValidationRule):
    """Reject windows where a required field is absent or not numeric."""

    REQUIRED_FIELDS = (
        "heart_rate",
        "skin_response",
        "temperature",
        "activity_level",
        "signal_quality",
    )

    def __init__(self):
        super().__init__("missing value")

    def check(self, observation):
        problems = []
        for field in self.REQUIRED_FIELDS:
            value = getattr(observation, field, None)
            if value is None:
                problems.append("{0} is missing".format(field))
            elif not isinstance(value, (int, float)) or isinstance(value, bool):
                # bool is a subclass of int in Python, so exclude it explicitly.
                problems.append("{0} is not a number".format(field))
        return problems


class ImpossibleValueRule(ValidationRule):
    """Reject windows holding values outside the physiological ranges."""

    def __init__(self):
        super().__init__("impossible value")

    def check(self, observation):
        problems = []

        checks = (
            ("heart_rate", observation.heart_rate, HEART_RATE_RANGE),
            ("temperature", observation.temperature, TEMPERATURE_RANGE),
            ("activity_level", observation.activity_level, ACTIVITY_LEVEL_RANGE),
            ("signal_quality", observation.signal_quality, SIGNAL_QUALITY_RANGE),
        )

        for field, value, bounds in checks:
            # Missing fields are skipped, MissingValueRule already flagged them.
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            lower, upper = bounds
            if value < lower or value > upper:
                problems.append(
                    "{0} of {1} is outside {2} to {3}".format(
                        field, value, lower, upper
                    )
                )

        skin = observation.skin_response
        if isinstance(skin, (int, float)) and not isinstance(skin, bool):
            if skin < SKIN_RESPONSE_MINIMUM:
                problems.append("skin_response of {0} is negative".format(skin))

        return problems


class SignalQualityRule(ValidationRule):
    """Reject windows the device reported low confidence in."""

    def __init__(self, minimum=MINIMUM_SIGNAL_QUALITY):
        super().__init__("low signal quality")
        self.minimum = minimum

    def check(self, observation):
        quality = observation.signal_quality
        if not isinstance(quality, (int, float)) or isinstance(quality, bool):
            return []
        if quality < self.minimum:
            return [
                "signal_quality of {0} is below the minimum of {1}".format(
                    quality, self.minimum
                )
            ]
        return []


class OrderedTimestampRule(ValidationRule):
    """Reject windows without a usable position in the session."""

    def __init__(self):
        super().__init__("bad timestamp")

    def check(self, observation):
        timestamp = observation.timestamp
        if not isinstance(timestamp, int) or isinstance(timestamp, bool):
            return ["timestamp is missing or not a whole number"]
        if timestamp < 0:
            return ["timestamp of {0} is negative".format(timestamp)]
        return []


class ObservationValidator:
    """Runs a collection of rules over every window in a session."""

    def __init__(self, rules=None):
        if rules is None:
            rules = [
                MissingValueRule(),
                ImpossibleValueRule(),
                SignalQualityRule(),
                OrderedTimestampRule(),
            ]
        self.rules = list(rules)

    def validate_observation(self, observation):
        problems = []
        for rule in self.rules:
            problems.extend(rule.check(observation))
        observation.record_validation(problems)
        return problems

    def validate_session(self, session):
        """Validate every window and return a summary dictionary."""
        problem_counts = {}
        for observation in session.observations:
            problems = self.validate_observation(observation)
            for problem in problems:
                label = _problem_label(problem)
                problem_counts[label] = problem_counts.get(label, 0) + 1

        usable = len(session.usable_observations())
        total = session.total_count

        return {
            "total_windows": total,
            "usable_windows": usable,
            "rejected_windows": total - usable,
            "usable_ratio": round(usable / total, 3) if total else 0.0,
            "problem_counts": problem_counts,
        }


def _problem_label(problem):
    """Strip the offending value from a message so problems can be counted."""
    if "is missing" in problem or "is not a number" in problem:
        return problem.split(" is ")[0] + " missing or unreadable"
    if "outside" in problem or "negative" in problem:
        return problem.split(" of ")[0] + " out of range"
    if "signal_quality" in problem:
        return "signal quality too low"
    return problem
