"""Console reports built from an analysis result dictionary."""


LINE_WIDTH = 66


def format_value(value, digits=2, missing="n/a"):
    """Render a number for the report, or a placeholder when it is None."""
    if value is None:
        return missing
    if isinstance(value, float):
        return "{0:.{1}f}".format(value, digits)
    return str(value)


def format_measurement_row(name, summary):
    """One row of the measurement table."""
    return "  {0:<16}{1:>10}{2:>10}{3:>10}".format(
        name,
        format_value(summary["average"]),
        format_value(summary["minimum"]),
        format_value(summary["maximum"]),
    )


def format_heading(text):
    return "\n" + text + "\n" + "-" * LINE_WIDTH


class SessionReport:
    """Standard report for one analysed session."""

    def __init__(self, result):
        self.result = result

    def title(self):
        return "{0} (participant {1})".format(
            self.result["label"], self.result["participant_id"]
        )

    def render(self):
        """Return the report as a single string."""
        parts = [
            "=" * LINE_WIDTH,
            self.title(),
            "=" * LINE_WIDTH,
            self._classification_block(),
            self._quality_block(),
            self._measurement_block(),
            self._comparison_block(),
        ]
        return "\n".join(part for part in parts if part)

    def _classification_block(self):
        lines = ["Classification: " + self.result["classification"].upper()]
        for reason in self.result["reasons"]:
            lines.append("  because " + reason)
        return "\n".join(lines)

    def _quality_block(self):
        quality = self.result["quality"]
        lines = [format_heading("Data quality")]
        lines.append("  {0} of {1} windows usable ({2}%)".format(
            quality["usable_windows"],
            quality["total_windows"],
            round(quality["usable_ratio"] * 100, 1),
        ))
        if quality["problem_counts"]:
            lines.append("  Reasons for rejection:")
            for problem, count in sorted(quality["problem_counts"].items()):
                lines.append("    {0:<40}{1:>3}".format(problem, count))
        return "\n".join(lines)

    def _measurement_block(self):
        if self.result["quality"]["usable_windows"] == 0:
            return format_heading("Measurements") + "\n  no usable windows to summarise"

        lines = [format_heading("Measurements (usable windows only)")]
        lines.append("  {0:<16}{1:>10}{2:>10}{3:>10}".format(
            "field", "average", "minimum", "maximum"))
        for name, summary in self.result["measurements"].items():
            lines.append(format_measurement_row(name, summary))
        return "\n".join(lines)

    def _comparison_block(self):
        comparison = self.result["comparison"]
        if comparison["heart_rate_above_baseline"] is None:
            return ""

        baselines = self.result["baselines"]
        trend = self.result["trend"]
        lines = [format_heading("Compared with personal baseline")]
        lines.append("  heart rate      {0} bpm above baseline of {1}".format(
            format_value(comparison["heart_rate_above_baseline"], 1),
            format_value(baselines["heart_rate"], 0),
        ))
        lines.append("  temperature     {0} C above baseline of {1}".format(
            format_value(comparison["temperature_above_baseline"], 2),
            format_value(baselines["temperature"], 2),
        ))
        lines.append("  skin response   {0} above baseline of {1}".format(
            format_value(comparison["skin_response_above_baseline"], 2),
            format_value(baselines["skin_response"], 2),
        ))
        lines.append("  trend           heart rate {0} bpm, activity {1}".format(
            format_value(trend["heart_rate_drop"], 1),
            format_value(trend["activity_drop"], 3),
        ))
        return "\n".join(lines)


class DetailedSessionReport(SessionReport):
    """Adds a per-window breakdown of every rejected observation.

    Overrides render and title. The extra detail is useful when investigating
    a sensor fault but too noisy for the standard summary.
    """

    def title(self):
        return super().title() + "  [detailed]"

    def render(self):
        """Extend the standard report with the rejected window list."""
        standard = super().render()
        detail = self._rejected_window_block()
        if not detail:
            return standard
        return standard + "\n" + detail

    def _rejected_window_block(self):
        rejected = self.result.get("rejected_detail", [])
        if not rejected:
            return ""

        lines = [format_heading("Rejected windows")]
        for window in rejected:
            lines.append("  window {0}".format(window["timestamp"]))
            for problem in window["problems"]:
                lines.append("    - " + problem)
        return "\n".join(lines)


def render_all(results, detailed=False):
    """Render a list of analysis results into one string."""
    report_class = DetailedSessionReport if detailed else SessionReport
    return "\n\n".join(report_class(result).render() for result in results)
