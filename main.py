"""Smart Fitness Session Analyzer.

Runs every demonstration scenario and prints a report for each one.

Usage:
    python3 main.py              standard reports
    python3 main.py --detailed   adds a per-window rejection breakdown
"""

import sys

from analysis import SessionAnalyzer
from reporting import render_all
from sample_data import build_all_sessions


def analyse_sessions(sessions, analyzer=None):
    """Run the analyzer over a list of sessions."""
    analyzer = analyzer or SessionAnalyzer()
    return [analyzer.analyze(session) for session in sessions]


def summary_table(results):
    """A one line per session overview, printed after the full reports."""
    lines = ["=" * 66, "Summary of all scenarios", "=" * 66]
    lines.append("{0:<32}{1:<20}{2:>12}".format("session", "classification", "usable"))
    lines.append("-" * 66)
    for result in results:
        quality = result["quality"]
        lines.append("{0:<32}{1:<20}{2:>12}".format(
            result["label"][:31],
            result["classification"],
            "{0}/{1}".format(quality["usable_windows"], quality["total_windows"]),
        ))
    return "\n".join(lines)


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    detailed = "--detailed" in argv

    sessions = build_all_sessions()
    results = analyse_sessions(sessions)

    print(render_all(results, detailed=detailed))
    print()
    print(summary_table(results))

    if not detailed:
        print("\nRun with --detailed to see why individual windows were rejected.")


if __name__ == "__main__":
    main()
