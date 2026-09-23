"""Reports what the supplied data generator actually produces.

This script is descriptive only. It does not choose thresholds and nothing in
the program imports it. Its purpose is to let anyone reproduce the figures the
README uses to justify the constants in analysis.py and validation.py.

Run it with: python3 calibration.py
"""

import statistics

from data_generator import available_scenarios, generate_fitness_data


SEEDS = range(1, 21)
WINDOW_COUNT = 12


def _numeric(values):
    """Keep only the numeric values, dropping None and non-numbers."""
    return [
        value for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]


def _halves(values):
    """Mean of the first half and mean of the last half."""
    half = len(values) // 2
    return statistics.mean(values[:half]), statistics.mean(values[-half:])


def collect(scenario):
    """Gather per-seed measurements for one scenario."""
    elevations = []
    activities = []
    heart_rate_drops = []
    activity_drops = []
    qualities = []

    for seed in SEEDS:
        profile, observations = generate_fitness_data(
            participant_id="P001",
            scenario=scenario,
            seed=seed,
            number_of_windows=WINDOW_COUNT,
        )
        baseline = profile["baseline_heart_rate"]

        heart_rates = _numeric([o["heart_rate"] for o in observations])
        levels = [v for v in _numeric([o["activity_level"] for o in observations]) if v >= 0]
        quality = _numeric([o["signal_quality"] for o in observations])

        if heart_rates:
            elevations.append(statistics.mean(heart_rates) - baseline)
        if levels:
            activities.append(statistics.mean(levels))
        if quality:
            qualities.append(statistics.mean(quality))

        if len(heart_rates) >= 4:
            early, late = _halves(heart_rates)
            heart_rate_drops.append(early - late)
        if len(levels) >= 4:
            early, late = _halves(levels)
            activity_drops.append(early - late)

    return {
        "heart_rate_elevation": elevations,
        "activity_level": activities,
        "heart_rate_drop": heart_rate_drops,
        "activity_drop": activity_drops,
        "signal_quality": qualities,
    }


def format_range(values, digits=1):
    """Format the min and max of a list of measurements."""
    if not values:
        return "n/a"
    return "{0:.{2}f} to {1:.{2}f}".format(min(values), max(values), digits)


def format_row(scenario, measurements):
    return "{0:<20}{1:>16}{2:>16}{3:>16}{4:>16}{5:>14}".format(
        scenario,
        format_range(measurements["heart_rate_elevation"]),
        format_range(measurements["activity_level"], 2),
        format_range(measurements["heart_rate_drop"]),
        format_range(measurements["activity_drop"], 3),
        format_range(measurements["signal_quality"], 2),
    )


def main():
    print("Generator behaviour across {0} seeds, {1} windows each".format(
        len(list(SEEDS)), WINDOW_COUNT))
    print("Ranges are min to max of the per-session means.\n")

    header = "{0:<20}{1:>16}{2:>16}{3:>16}{4:>16}{5:>14}".format(
        "scenario", "hr above base", "activity", "hr drop", "activity drop",
        "signal qual")
    print(header)
    print("-" * len(header))

    for scenario in available_scenarios():
        print(format_row(scenario, collect(scenario)))

    print("\nhr drop is the mean of the first half minus the mean of the last")
    print("half, so a large positive number means the session declined.")


if __name__ == "__main__":
    main()
