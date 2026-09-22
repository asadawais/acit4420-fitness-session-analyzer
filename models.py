"""Domain classes for the Smart Fitness Session Analyzer.

Three classes live here:

Participant  holds a person and their personal reference measurements.
Observation  holds one measurement window from the wearable device.
Session      groups a Participant together with a list of Observations.

Session demonstrates composition. A Session owns its Participant and its
Observation objects, and those objects have no meaning outside the session
they belong to.
"""


class Participant:
    """A person taking part in a training session.

    The baseline values are personal reference measurements. Two people can
    produce very different raw numbers during the same exercise, so every
    comparison in this program is made against the person's own baseline
    rather than against a fixed number.

    The baselines are stored in protected attributes and exposed through
    read-only properties. Once a participant is created the reference values
    must not be edited by accident, because every later calculation depends
    on them.
    """

    def __init__(self, participant_id, baseline_heart_rate,
                 baseline_skin_response, baseline_temperature):
        if not isinstance(participant_id, str) or not participant_id.strip():
            raise ValueError("participant_id must be a non-empty string")

        self._participant_id = participant_id.strip()
        self._baseline_heart_rate = float(baseline_heart_rate)
        self._baseline_skin_response = float(baseline_skin_response)
        self._baseline_temperature = float(baseline_temperature)

    @classmethod
    def from_profile(cls, profile):
        """Build a Participant from the generator's profile dictionary.

        This is a class method because it is an alternative constructor. The
        data generator hands back a plain dictionary, and this keeps the
        knowledge of that dictionary layout in one place instead of spreading
        it across the program. If the generator ever changed its field names,
        only this method would need updating.
        """
        if not isinstance(profile, dict):
            raise TypeError("profile must be a dictionary")

        required = (
            "participant_id",
            "baseline_heart_rate",
            "baseline_skin_response",
            "baseline_temperature",
        )
        missing = [field for field in required if field not in profile]
        if missing:
            raise KeyError("profile is missing fields: " + ", ".join(missing))

        return cls(
            profile["participant_id"],
            profile["baseline_heart_rate"],
            profile["baseline_skin_response"],
            profile["baseline_temperature"],
        )

    @property
    def participant_id(self):
        return self._participant_id

    @property
    def baseline_heart_rate(self):
        return self._baseline_heart_rate

    @property
    def baseline_skin_response(self):
        return self._baseline_skin_response

    @property
    def baseline_temperature(self):
        return self._baseline_temperature

    def heart_rate_above_baseline(self, heart_rate):
        """Return how far a measured heart rate sits above this person's rest."""
        return heart_rate - self._baseline_heart_rate

    def temperature_above_baseline(self, temperature):
        return temperature - self._baseline_temperature

    def skin_response_above_baseline(self, skin_response):
        return skin_response - self._baseline_skin_response

    def __repr__(self):
        return (
            "Participant(id={0!r}, baseline_hr={1:.0f})".format(
                self._participant_id, self._baseline_heart_rate
            )
        )


class Observation:
    """One measurement window produced by the wearable device.

    An Observation stores the raw values exactly as they arrived, including
    missing or impossible ones. It does not clean or correct anything. The
    validation rules in validation.py decide whether a window is usable, and
    the outcome is recorded on the object afterwards.

    Keeping the raw values means the report can say how many windows were
    rejected and why, instead of silently dropping them.
    """

    def __init__(self, timestamp, heart_rate, skin_response, temperature,
                 activity_level, signal_quality):
        self.timestamp = timestamp
        self.heart_rate = heart_rate
        self.skin_response = skin_response
        self.temperature = temperature
        self.activity_level = activity_level
        self.signal_quality = signal_quality

        # Filled in by the validator. Until then the window is untested.
        self._is_usable = None
        self._problems = []

    @classmethod
    def from_dict(cls, raw):
        """Build an Observation from one generator dictionary.

        Missing keys become None rather than raising, because a window with a
        missing field is exactly the kind of bad data this program is supposed
        to detect and report. Refusing to build the object would hide the
        problem instead of counting it.
        """
        if not isinstance(raw, dict):
            raise TypeError("observation must be a dictionary")

        return cls(
            timestamp=raw.get("timestamp"),
            heart_rate=raw.get("heart_rate"),
            skin_response=raw.get("skin_response"),
            temperature=raw.get("temperature"),
            activity_level=raw.get("activity_level"),
            signal_quality=raw.get("signal_quality"),
        )

    @property
    def is_usable(self):
        """True only after validation has run and the window passed."""
        return self._is_usable is True

    @property
    def is_validated(self):
        return self._is_usable is not None

    @property
    def problems(self):
        """A copy of the problem list, so callers cannot edit the original."""
        return list(self._problems)

    def record_validation(self, problems):
        """Store the outcome of validation on this window.

        An empty problem list means the window is usable.
        """
        self._problems = list(problems)
        self._is_usable = len(self._problems) == 0

    def as_dict(self):
        """Return the window as a dictionary, including its validation state."""
        return {
            "timestamp": self.timestamp,
            "heart_rate": self.heart_rate,
            "skin_response": self.skin_response,
            "temperature": self.temperature,
            "activity_level": self.activity_level,
            "signal_quality": self.signal_quality,
            "usable": self.is_usable,
            "problems": self.problems,
        }

    def __repr__(self):
        state = "unchecked"
        if self.is_validated:
            state = "usable" if self.is_usable else "rejected"
        return "Observation(t={0}, hr={1}, {2})".format(
            self.timestamp, self.heart_rate, state
        )


class Session:
    """A complete training session for one participant.

    This is the composition example. A Session is built from a Participant
    object and a list of Observation objects. It does not store loose numbers
    copied out of them, it holds the objects themselves and asks them for what
    it needs.

    The session keeps its observation list protected so that windows cannot be
    added after validation has run, which would leave the counts in the report
    disagreeing with the data.
    """

    def __init__(self, participant, observations, label="session"):
        if not isinstance(participant, Participant):
            raise TypeError("participant must be a Participant object")

        observations = list(observations)
        for item in observations:
            if not isinstance(item, Observation):
                raise TypeError("every observation must be an Observation object")

        self.participant = participant
        self.label = label
        self._observations = observations

    @classmethod
    def from_generator_output(cls, profile, raw_observations, label="session"):
        """Build a full Session straight from the generator's two return values."""
        participant = Participant.from_profile(profile)
        observations = [Observation.from_dict(raw) for raw in raw_observations]
        return cls(participant, observations, label=label)

    @property
    def observations(self):
        """A copy of the window list, so the session contents stay fixed."""
        return list(self._observations)

    @property
    def total_count(self):
        return len(self._observations)

    def usable_observations(self):
        """Only the windows that passed validation, in their original order."""
        return [item for item in self._observations if item.is_usable]

    def rejected_observations(self):
        return [
            item for item in self._observations
            if item.is_validated and not item.is_usable
        ]

    def __len__(self):
        return len(self._observations)

    def __repr__(self):
        return "Session(label={0!r}, participant={1!r}, windows={2})".format(
            self.label, self.participant.participant_id, self.total_count
        )
