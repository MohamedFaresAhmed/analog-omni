# Analog Omni

Analog Omni is an open-source Python tool that will size analog amplifier blocks from specs, prove every result in a simulator, and explain it in formulas, with an AI layer that works inside whichever assistant you prefer. A numeric small-signal solver does all evaluation; symbolic analysis is used only to explain a result. The public tests run on ngspice and an open PDK, so using Omni needs no commercial licence.

**Status: pre-alpha.** The `analog_omni` package is an empty skeleton with no production code yet. The repository holds reference data and its tests:

- `tests/fixtures/legacy/`: small-signal reference fixtures for six circuits (one- and two-transistor MOSFET circuits, a five-transistor OTA, a two-stage Miller OTA, a folded-cascode OTA and a fully differential two-stage OTA), exported once from an earlier MATLAB small-signal analyser. Each file holds the circuit as a component list, its parameter values, the G, C and B matrices and the transfer function sampled at the listed frequencies.
- `tests/test_legacy_fixtures.py`: an independent NumPy check that re-stamps each circuit from its component list and reproduces every stored sample.
- `examples/netlists/`: four example netlists with generic device names. Three are in Spectre syntax; `CS_Amp.txt` is a SLiCAP-style small-signal netlist, in which the MOS device is given by its small-signal parameters rather than a model.

## Data responsibility

- Omni sends nothing anywhere by itself.
- Tool results may reach whatever AI service you connect to Omni.
- You are responsible for following your own PDK agreement.

[DATA_POLICY.md](DATA_POLICY.md) states these three points in full.

## Running the tests

Omni needs Python 3.11 or newer. From the repository root, create a virtual environment, install the package in editable mode with its test extra (NumPy and pytest), and run the tests:

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux and macOS
python -m pip install -e ".[test]"
python -m pytest
```

Run only the activate line for your system. CI runs the same tests on Python 3.11 and 3.13, on Ubuntu and Windows, for every push and pull request.

## Licence

Apache-2.0, see [LICENSE](LICENSE).
