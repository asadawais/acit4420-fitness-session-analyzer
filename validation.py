"""Validation rules for individual observation windows.

This module is where inheritance and method overriding are used. There is one
base class, ValidationRule, and several subclasses that each override the
check method with a different test.

Inheritance earns its place here because every rule answers the same question
in the same shape. Given one window, what is wrong with it? The base class
fixes that shape and handles the shared parts, such as the rule name and the
wording of the message. Each subclass only has to supply the test itself.

A rule returns a list of problem descriptions. An empty list means the rule
found nothing wrong. Returning a list rather than True or False lets a single
window report several problems at once, which matters for the poor-quality
data where a window can be both badly measured and missing a field.
"""


# A window measured while the sensor had poor contact is not trustworthy even
# if the numbers themselves look plausible. The clean scenarios in the data
# generator sit between 0.82 and 0.99, and the poor-quality scenario sits
# between 0.05 and 0.55, so 0.60 separates them with room on both sides.
MINIMUM_SIGNAL_QUALITY = 0.60

# Physiologically possible ranges. Anything outside these is a sensor fault
# rather than an unusual person. The ranges follow DATA_DESCRIPTION.md.
HEART_RATE_RANGE = (35, 205)
TEMPERATURE_RANGE = (25.0, 42.0)
ACTIVITY_LEVEL_RANGE = (0.0, 1.0)
SIGNAL_QUALITY_RANGE = (0.0, 1.0)
SKIN_RESPONSE_MINIMUM = 0.0


class ValidationRule:
    """Base class for every validation rule.

    Subclasses override check and return a list of strings describing what is
    wrong with the window. This class is not meant to be used directly. Its
    own check raises, so that a subclass which forgets to override it fails
    loudly during development instead of quietly passing every window.
    """

    def __init__(self, name):
        self.name = name

    def check(self, observation):
        raise NotImplementedError("each rule must implement check")

    def describe(self):
        return self.name

    def __repr__(self):
        return "{0}(name={1!r})".format(type(self).__name__, self.name)


class MissingValueRule(ValidationRule):
    """Reject windows where a required field is absent.

    The generator sets heart_rate and skin_response to None in the
    poor-quality scenario. A missing measurement cannot be estimated or filled
    in, so the window is rejected rather than guessed at.
    """

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
                problems.append("{0} is not a number".format(field))
        return problems


class ImpossibleValueRule(ValidationRule):
    """Reject windows holding values a real body cannot produce.

    The generator injects a heart rate of 265 and an activity level of -0.20
    in the poor-quality scenario. Both are outside what the sensor could
    legitimately measure, so they indicate a fault in the device rather than
    an unusual session.

    Fields that are missing are skipped here. MissingValueRule has already
    reported those, and reporting the same window twice for one underlying
    fault would make the rejection counts harder to read.
    """

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
    """Flag windows the device itself reported low confidence in.

    This rule is different from the other two. The numbers may look entirely
    reasonable, but the device is telling us it was not measuring well. Using
    such a window would let plausible-looking noise into the averages.
    """

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
    """Reject windows without a usable position in the session.

    Recovery is detected by comparing the start of a session with its end, so
    a window that cannot be placed in order is not safe to include even if its
    measurements are fine.
    """

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
    """Runs a collection of rules over every window in a session.

    The validator holds rules rather than inheriting from them, because it is
    not itself a rule. It is composition again at a smaller scale. Adding a new
    rule means writing one subclass and putting it in this list, without
    touching the session, the analysis or the report.
    """

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
        """Run every rule over one window and record the outcome on it."""
        problems = []
        for rule in self.rules:
            problems.extend(rule.check(observation))
        observation.record_validation(problems)
        return problems

    def validate_session(self, session):
        """Validate every window in a session.

        Returns a dictionary summarising what happened, which later becomes
        part of the structured analysis result.
        """
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
    """Group similar problem messages so the report can count them.

    The individual messages carry the offending value, which is useful when
    reading one window but unhelpful when counting across a session. This
    strips the message back to the field and the kind of fault.
    """
    if "is missing" in problem or "is not a number" in problem:
        return problem.split(" is ")[0] + " missing or unreadable"
    if "outside" in problem or "negative" in problem:
        return problem.split(" of ")[0] + " out of range"
    if "signal_quality" in problem:
        return "signal quality too low"
    return problem
