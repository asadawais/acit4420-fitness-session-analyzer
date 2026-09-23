# Smart Fitness Session Analyzer

Option A, ACIT4420 Problem-solving with scripting, assignment I.

Asad Mohammad Awais, S374979.

## What it does

The program takes simulated wearable data from the supplied generator, throws
out the measurement windows that are broken, summarises what is left, compares
it against the participant's own resting values and then says what kind of
session it was. Resting, moderate activity, high activity, recovering, or
insufficient data if there is not enough left to say anything.

It always prints why it landed on that answer.

Standard library only, no installs.

## Running it

```
python3 main.py
```

Run it from the project folder, the one holding `main.py`.

If `python3` does not work on your machine, use `python main.py`.

Other things you can run:

```
python3 main.py --detailed
python3 tests.py
python3 calibration.py
```

`--detailed` adds a list of every rejected window and what was wrong with it.
`tests.py` runs 52 unit tests. `calibration.py` prints the measurements I used
to pick the thresholds, more on that below.

`requirements.txt` has no packages in it because there are no dependencies.

## Files

| File | What it does |
|---|---|
| `main.py` | Entry point, runs every scenario and prints the reports |
| `models.py` | Participant, Observation, Session |
| `validation.py` | The rules that decide if a window is usable |
| `analysis.py` | Statistics, recovery detection, classification |
| `reporting.py` | Turns a result into console output |
| `sample_data.py` | The scenarios, and the only file that calls the generator |
| `calibration.py` | Prints what the generator actually produces |
| `tests.py` | Tests |
| `data_generator.py` | Supplied with the assignment, I have not touched it |

I split it into modules instead of one big file so each one has a single job.
Only `sample_data.py` talks to `data_generator.py`, so if the data came from a
real device that is the only file I would need to rewrite.

`calibration.py` is not part of the program and nothing imports it. I wrote it
so the numbers further down can be checked by running it, instead of just
having to take my word for them.

## Classes

| Class | What it is responsible for |
|---|---|
| `Participant` | A person and their baseline heart rate, skin response and temperature |
| `Observation` | One measurement window, kept exactly as it came in, faults and all |
| `Session` | A participant plus the windows from one training session |
| `ValidationRule` | Base class, defines what a rule looks like |
| `MissingValueRule` | Fields that are absent or not numbers |
| `ImpossibleValueRule` | Values a body cannot produce |
| `SignalQualityRule` | Windows the device flagged as badly measured |
| `OrderedTimestampRule` | Windows with no usable position in the session |
| `ObservationValidator` | Runs the rules over every window |
| `SessionAnalyzer` | Validates, summarises, compares to baseline, classifies |
| `SessionReport` | Renders a result as text |
| `DetailedSessionReport` | Same but with the rejected windows listed |

### Composition

`Session` is the main one. You build it from a `Participant` object and a list
of `Observation` objects, and it keeps those objects instead of copying numbers
out of them. `SessionAnalyzer` then goes through the session to reach them, so
when it needs a baseline it asks the participant and when it needs to know if a
window is usable it asks the window. Nothing copies those values around.

`ObservationValidator` holds a list of rule objects rather than inheriting from
them, because a validator is not itself a rule. That way adding a new rule means
writing one subclass and adding it to the list, and nothing else in the program
changes.

`SessionAnalyzer` holds a validator for the same reason.

### Encapsulation

`Participant` keeps its three baselines in protected attributes with read-only
properties and no setter. Everything in the program compares against those
values, so letting them be changed halfway through would quietly break the
results. There is a test that checks assigning to `baseline_heart_rate` raises.

`Observation` keeps `_is_usable` and `_problems` protected. They can only be set
through `record_validation`. The `problems` property hands back a copy so
nothing outside can append to the real list.

`Session` returns a copy of its window list for the same reason. If windows
could be added after validation ran, the counts in the report would not match
the data.

### Inheritance and overriding

Two places.

The validation rules are the main one. `ValidationRule` sets the shape every
rule shares, which is a name and a `check` method that takes a window and
returns a list of problems. Each of the four subclasses overrides `check` and
inherits the rest. The base class `check` raises `NotImplementedError` so if I
ever add a rule and forget to override it, it breaks loudly instead of passing
every window.

I went with inheritance here rather than composition because all four rules
really do answer the same question in the same shape, and the validator does
not need to know which one it is holding.

The other is `DetailedSessionReport`, which extends `SessionReport` and
overrides `render` and `title`. Its `render` calls `super().render()` and then
adds the rejected window list on the end. Keeps the normal report short and the
detailed one there when you need to dig into a sensor fault.

### Class methods

`Participant.from_profile`, `Observation.from_dict` and
`Session.from_generator_output` are alternative constructors that take the
generator's dictionaries and build objects out of them. Having them as class
methods keeps all the knowledge of the dictionary layout in three places
instead of scattered everywhere. If the field names changed I would only have
to fix those.

### Standalone functions

`average`, `minimum_and_maximum`, `summarise`, `split_half_difference` and
`percentage` in `analysis.py` do the maths. `format_value`,
`format_measurement_row`, `format_heading` and `render_all` in `reporting.py`
handle the printing. None of them need the classes, which makes them easy to
test on their own.

## Validation

A window gets rejected if any of these are true:

| Rule | When it fires |
|---|---|
| Missing value | Any of the five fields is `None` or not a number |
| Impossible value | Heart rate outside 35 to 205, temperature outside 25 to 42, activity level or signal quality outside 0 to 1, or negative skin response |
| Low signal quality | Signal quality under 0.60 |
| Bad timestamp | Missing, not a whole number, or negative |

The ranges are from `DATA_DESCRIPTION.md`.

The 0.60 cutoff I got from the generator itself. The four clean scenarios give
session mean signal quality between 0.88 and 0.93, and the poor quality one
gives 0.23 to 0.40. There is a big empty gap between those, so anywhere in the
middle works and 0.60 is not a number I had to tune.

Rejected windows are kept, not deleted, so the report can say how many went and
why. Dropping them quietly would hide the problem.

`ImpossibleValueRule` skips fields that are missing, since `MissingValueRule`
already caught those and counting the same fault twice makes the report
confusing to read.

## Classification

The order these are checked in matters, and it was the main thing I had to
think about.

**1. Insufficient data.** Under 4 usable windows, or under half the original
windows surviving. Too thin to say anything honest about, so it says that
instead of guessing.

**2. Recovering.** Heart rate down at least 15 bpm and activity down at least
0.25, comparing the first half of the session against the last half. Both have
to be true.

**3. Intensity**, from mean heart rate above the person's own baseline.

| Result | Heart rate above baseline |
|---|---|
| Resting | under 12 bpm |
| Moderate activity | 12 to 45 |
| High activity | 45 and up |

### Why recovery comes before intensity

This is the part worth explaining. A recovering session averages out somewhere
between a moderate and a high one, so the averages cannot tell them apart. Only
the decline can. If I checked intensity first, every recovery session would come
out as high or moderate activity and the decline would never get looked at.

Here is what `calibration.py` gives over 20 seeds. Each column is the range of
the per-session means.

| Scenario | HR above baseline | HR drop | Activity drop |
|---|---|---|---|
| resting | 0.8 to 3.2 | -3.0 to 3.5 | -0.043 to 0.062 |
| moderate | 25.7 to 30.2 | -6.2 to 7.0 | -0.073 to 0.100 |
| high | 54.5 to 61.4 | -8.8 to 10.5 | -0.070 to 0.095 |
| recovery | 33.8 to 37.8 | 24.2 to 36.3 | 0.347 to 0.472 |

Look at the first column and recovery is sitting right between moderate and
high. Look at the last two and it is nowhere near any of them.

So I put the thresholds in the gaps. A steady session drops at most 10.5 bpm by
chance and a recovering one drops at least 24.2, so 15 sits between them with
room either side. Same for activity, where the gap runs 0.100 to 0.347 and I
used 0.25. The intensity cutoffs of 12 and 45 sit in the gaps between 3.2 and
25.7, and between 30.2 and 54.5.

I tested it over 60 seeds and four different window counts, 1200 sessions, and
every single one came out as the scenario that made it.

## Assumptions

- The baseline values are correct. Nothing in the data lets me check them so I
  take them as given.
- Windows arrive in order. They do in the supplied data, and recovery detection
  needs it.
- A window is usable or it is not. No partial credit for one bad field, because
  you cannot work out a heart rate from the other measurements.
- Everything is compared to the person's own baseline instead of fixed numbers,
  since the same heart rate means different things for different people.
- The five generator scenarios cover every session type I need to handle.

## Example output

```
==================================================================
Resting session (participant P001)
==================================================================
Classification: RESTING
  because heart rate averaged 2.0 bpm above the personal baseline
  because no sustained decline, heart rate rose 1.333 bpm between the first half and the last

Data quality
------------------------------------------------------------------
  12 of 12 windows usable (100.0%)

Measurements (usable windows only)
------------------------------------------------------------------
  field              average   minimum   maximum
  heart_rate              80        76        85
  activity_level        0.11      0.04      0.18
  temperature          32.78     32.68     32.94
  skin_response         1.19      0.97      1.32

Compared with personal baseline
------------------------------------------------------------------
  heart rate      2.0 bpm above baseline of 78
  temperature     0.02 C above baseline of 32.76
  skin response   0.02 above baseline of 1.17
  trend           heart rate -1.3 bpm, activity 0.007
```

The table at the end of a full run:

```
==================================================================
Summary of all scenarios
==================================================================
session                         classification            usable
------------------------------------------------------------------
Resting session                 resting                    12/12
Moderate activity               moderate activity          12/12
High activity                   high activity              12/12
Activity followed by recovery   recovering                 12/12
Poor-quality sensor data        insufficient data           0/12
Empty session                   insufficient data            0/0
Single usable window            insufficient data            1/1
Every window faulty             insufficient data            0/4
Under half the windows usable   insufficient data            4/9
```

And with `--detailed`, the poor quality session gets this:

```
Rejected windows
------------------------------------------------------------------
  window 0
    - heart_rate is missing
    - signal_quality of 0.07 is below the minimum of 0.6
  window 1
    - heart_rate of 265 is outside 35 to 205
    - signal_quality of 0.41 is below the minimum of 0.6
```

## Scenarios

The five required ones from the generator, plus four I built by hand in
`sample_data.py`:

| Scenario | Where from | Result |
|---|---|---|
| Resting | generator | resting |
| Moderate activity | generator | moderate activity |
| High activity | generator | high activity |
| Activity followed by recovery | generator | recovering |
| Poor-quality sensor data | generator | insufficient data |
| Empty session | hand-built | insufficient data, no crash |
| Single usable window | hand-built | insufficient data |
| Every window faulty | hand-built | insufficient data, all four rules fire |
| Under half the windows usable | hand-built | insufficient data, 4 of 9 survive |

The generator always gives at least six reasonably shaped windows, so it cannot
produce an empty session or a one window session. Those still need to not crash
the program, which is why I made them myself.

The last one exists because there are two ways to end up with insufficient data.
Too few usable windows is one, and enough windows but under half of them
surviving is the other. The generator never produces the second, so I built a
session where 4 of 9 survive to make sure that path works and says something
sensible.

## Limitations

- The thresholds are fitted to this generator. Real data would need them
  redone, which is what `calibration.py` is there for.
- Recovery is first half against last half. A session that went up and came back
  down to where it started would not be caught, and neither would a drop that
  only happens in the last two or three windows.
- The poor quality scenario ends up as insufficient data because every window
  fails validation. If a session had usable but very noisy windows, big random
  swings could in theory look like a decline. It never happens with this data
  because the low signal quality strips those windows out first, but I am not
  guarding against it beyond that.
- Validation checks the values, not whether they are consistent with each
  other. A window with a resting heart rate and a very high activity level is
  physically odd but passes, because each field is fine on its own.
- No way to tell a sensor fault from someone taking the device off mid session.
  Both just show up as rejected windows.
- This is thresholds, not a model. It tells you which band a session falls in
  and gives no confidence number.
- Only the five scenarios are recognised. Anything outside them gets forced into
  the closest band.
