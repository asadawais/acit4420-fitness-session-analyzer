"""Domain classes: Participant, Observation and Session."""


class Participant:
    """A person and their personal reference measurements."""

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
        """Build a Participant from the generator's profile dictionary."""
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

        for field in required[1:]:
            value = profile[field]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(
                    "{0} must be a number, got {1!r}".format(field, value)
                )

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
        return heart_rate - self._baseline_heart_rate

    def temperature_above_baseline(self, temperature):
        return temperature - self._baseline_temperature

    def skin_response_above_baseline(self, skin_response):
        return skin_response - self._baseline_skin_response

    def __repr__(self):
        return "Participant(id={0!r}, baseline_hr={1:.0f})".format(
            self._participant_id, self._baseline_heart_rate
        )


class Observation:
    """One measurement window, stored exactly as it arrived."""

    def __init__(self, timestamp, heart_rate, skin_response, temperature,
                 activity_level, signal_quality):
        self.timestamp = timestamp
        self.heart_rate = heart_rate
        self.skin_response = skin_response
        self.temperature = temperature
        self.activity_level = activity_level
        self.signal_quality = signal_quality

        self._is_usable = None
        self._problems = []

    @classmethod
    def from_dict(cls, raw):
        """Build an Observation from one generator dictionary.

        Missing keys become None instead of raising, so a faulty window can be
        counted and reported rather than crashing the run.
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
        return self._is_usable is True

    @property
    def is_validated(self):
        return self._is_usable is not None

    @property
    def problems(self):
        return list(self._problems)

    def record_validation(self, problems):
        """Store the validation outcome. An empty list means the window passed."""
        self._problems = list(problems)
        self._is_usable = len(self._problems) == 0

    def __repr__(self):
        state = "unchecked"
        if self.is_validated:
            state = "usable" if self.is_usable else "rejected"
        return "Observation(t={0}, hr={1}, {2})".format(
            self.timestamp, self.heart_rate, state
        )


class Session:
    """A training session, built from a Participant and its Observations."""

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
        participant = Participant.from_profile(profile)
        observations = [Observation.from_dict(raw) for raw in raw_observations]
        return cls(participant, observations, label=label)

    @property
    def observations(self):
        # Returns a copy so windows cannot be added after validation has run.
        return list(self._observations)

    @property
    def total_count(self):
        return len(self._observations)

    def usable_observations(self):
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
