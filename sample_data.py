"""Scenario definitions. The only module that calls data_generator."""

from data_generator import available_scenarios, generate_fitness_data
from models import Observation, Participant, Session


# Fixed seeds keep the console output reproducible between runs.
GENERATOR_SCENARIOS = (
    ("Resting session", "resting", 42),
    ("Moderate activity", "moderate_activity", 42),
    ("High activity", "high_activity", 42),
    ("Activity followed by recovery", "recovery", 42),
    ("Poor-quality sensor data", "poor_quality", 42),
)

DEFAULT_WINDOW_COUNT = 12


def build_session_from_generator(label, scenario, seed=42,
                                 number_of_windows=DEFAULT_WINDOW_COUNT,
                                 participant_id="P001"):
    """Call the generator once and wrap the result in a Session."""
    profile, raw_observations = generate_fitness_data(
        participant_id=participant_id,
        scenario=scenario,
        seed=seed,
        number_of_windows=number_of_windows,
    )
    return Session.from_generator_output(profile, raw_observations, label=label)


def build_required_sessions():
    """The five scenarios the assignment asks for."""
    return [
        build_session_from_generator(label, scenario, seed)
        for label, scenario, seed in GENERATOR_SCENARIOS
    ]


def build_edge_case_sessions():
    """Small sessions the generator cannot produce, since it always returns
    at least six reasonably shaped windows."""
    participant = Participant(
        participant_id="P999",
        baseline_heart_rate=70,
        baseline_skin_response=1.8,
        baseline_temperature=32.4,
    )

    empty_session = Session(participant, [], label="Empty session")

    single_window = Session(
        participant,
        [
            Observation(
                timestamp=0,
                heart_rate=112,
                skin_response=2.4,
                temperature=33.1,
                activity_level=0.61,
                signal_quality=0.94,
            )
        ],
        label="Single usable window",
    )

    # One window per rule, so all four fire at least once.
    all_broken = Session(
        participant,
        [
            Observation(0, None, 2.1, 32.9, 0.50, 0.91),
            Observation(1, 265, 2.2, 33.0, 0.55, 0.90),
            Observation(2, 120, -1.0, 33.1, -0.20, 0.88),
            Observation(3, 118, 2.3, 55.0, 0.52, 0.12),
        ],
        label="Every window faulty",
    )

    return [empty_session, single_window, all_broken]


def build_all_sessions():
    """Every scenario the program demonstrates, in report order."""
    return build_required_sessions() + build_edge_case_sessions()


def generator_scenario_names():
    return available_scenarios()
