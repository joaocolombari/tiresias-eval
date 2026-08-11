# Bisgaard/CAMFIT prescription experiment

This directory contains a reproducible prescription baseline for comparing
Tiresias with the Clarity CEC1 openMHA hearing-aid chain. It generates the
compressive CAMFIT fitting for all ten standard Bisgaard audiograms (N1–N7 and
S1–S3), for two identical ears.

The important distinction is:

- the **prescription output** is a gain-versus-input-level curve for each
  frequency band and ear;
- the **compressor timing and detector settings** are fixed properties of the
  CEC1 implementation, not outputs inferred from the audiogram.

Therefore, copying only one gain value or one compression ratio per band does
not reproduce the openMHA reference.

## Reproduce the generated files

The isolated Python installation and pinned pyClarity source are described in
[`../../tools/clarity/README.md`](../../tools/clarity/README.md). From the
workspace root, run:

```bash
tools/clarity/.venv/bin/python \
  experiments/prescriptions/scripts/generate_camfit_prescriptions.py
```

Run the offline openMHA check with:

```bash
tools/clarity/.venv/bin/python \
  experiments/prescriptions/scripts/run_openmha_smoke_test.py --profile N3
```

The generator validates the dimensions and symmetry of every prescription,
checks that every input/output curve is monotonic, and checks the 100 dB SPL
output ceiling. `generated/SHA256SUMS.txt` makes accidental changes detectable.

## Inputs to the prescription

For each ear, CAMFIT receives:

1. Audiometric frequencies in Hz.
2. Hearing thresholds at those frequencies in dB HL.
3. The fixed Clarity fitting-band centres.
4. The input-level grid over which gain must be calculated.
5. Noise-gate thresholds and slope.
6. The maximum allowed band output level.

The Bisgaard input table is
[`data/bisgaard_2010_audiograms.csv`](data/bisgaard_2010_audiograms.csv):

```text
frequencies = [250, 375, 500, 750, 1000, 1500, 2000, 3000, 4000, 6000] Hz
profiles    = N1, N2, N3, N4, N5, N6, N7, S1, S2, S3
```

The generated listener is deliberately symmetric: the selected Bisgaard curve
is supplied to both ears. That makes left/right equality an additional
integrity check and avoids introducing an arbitrary asymmetry.

pyClarity resamples the audiogram at the fitting-band centres and holds the
nearest endpoint outside the measured range. Thus, this experiment holds the
250 Hz threshold below 250 Hz and the 6000 Hz threshold above 6000 Hz. AMT's
`standardaudiogram` instead uses log-frequency linear interpolation and
extrapolation when queried at other frequencies. This policy difference is
recorded because it affects 177, 6727, and 11314 Hz.

The complete fixed settings are in
[`config/camfit_cec1.json`](config/camfit_cec1.json). The central ones are:

| Setting | CEC1 value |
|---|---:|
| sample rate | 44,100 Hz |
| input calibration | 0 dBFS = 100 dB SPL |
| output calibration | 0 dBFS = 120 dB SPL |
| CAMFIT maximum band output | 100 dB SPL |
| gain-table inputs | -10 to 110 dB SPL, 1 dB steps |
| attack time constant | 20 ms |
| decay/release time constant | 100 ms |
| short-time RMS averaging constant | 100 ms |

The 20 dB difference between input and output calibration is intentional
headroom. A digital output/input ratio read directly in dBFS is therefore 20 dB
smaller than the calibrated acoustic gain.

## Exact prescription outputs

For each Bisgaard profile, the authoritative output is an `18 x 121` matrix:

```text
18 rows = 9 bands x 2 ears
121 columns = input levels -10, -9, ..., 110 dB SPL
cell value = gain in dB
output level in a band = input level + gain
```

These data are available in three representations:

- [`generated/gain_table_long.csv`](generated/gain_table_long.csv): all 21,780
  cells in tidy tabular form;
- `generated/prescriptions/<profile>.json`: one self-contained prescription per
  Bisgaard profile;
- `generated/openmha_cfg/`: directly runnable openMHA configurations.

[`generated/sigma_compact_targets.csv`](generated/sigma_compact_targets.csv)
adds gain at 45, 65, and 85 dB SPL, an inferred compression ratio, the output
limiter knee, and timing settings. It is an implementation aid, not a lossless
replacement for the full table.

### What does *not* come out of CAMFIT

CAMFIT does **not** generate attack time, release time, detector averaging time,
or a filter order. In the CEC1 recipe these are separately fixed at 20 ms,
100 ms, and 100 ms, respectively. Consequently:

- the list of gains alone is insufficient;
- one gain plus one ratio per band is only an approximation;
- copying the full per-band curve and reproducing the level detector is the
  closest implementation.

CAMFIT itself computes a broadband fitting from the audiogram, LTASS speech
statistics, absolute hearing threshold conversion, and a compression ratio per
band. It then evaluates gain on the full -10...110 dB SPL grid. Negative
insertion gains are suppressed, and gain is reduced at high input levels so the
band output does not exceed 100 dB SPL. The generated gain table can therefore
contain negative values near its upper end: those values implement limiting and
must not be clipped back to zero in SigmaStudio.

Below each band-specific noise-gate threshold
`[38, 38, 36, 37, 32, 26, 23, 22, 8] dB SPL`, the configured slope is zero.
Here this does not mute the signal: it holds the gain constant at the gain found
at the threshold, producing a 1:1 input/output slope below it.

## openMHA filter bank

The CEC1 filter bank is not an octave IIR bank and is not Linkwitz–Riley. It is
a linear-phase, FFT-domain bank inside an overlap-add chain:

```text
sample rate        44.1 kHz
block/hop          64 samples
analysis window    128-sample Hann
FFT                256 samples
window position    0.5 (symmetric)
frequency scale    logarithmic
band overlap       rectangular
band specification centre-frequency mode
phase mode         linear phase
```

The nine centre frequencies are:

```text
[177, 297, 500, 841, 1414, 2378, 4000, 6727, 11314] Hz
```

The corresponding boundaries at 44.1 kHz are:

```text
[0, 229.2793, 385.3570, 648.4597, 1090.5, 1833.7,
 3084.2, 5187.3, 8724.1, 22050] Hz
```

The lowest and highest bands extend to DC and Nyquist. In the Clarity fitting,
the ninth row for each ear is forced to 0 dB. It is a unity high-frequency
boundary path, not a muted path; there are eight prescription-active bands and
nine signal paths.

After per-band gain, `smoothgains_bridge` constrains the effective impulse
response to the overlap-add zero-padding length. This preserves the selected
linear-phase mode and reduces circular-aliasing artefacts.

## openMHA dynamic compressor

For every block and frequency band, the `dc` plugin estimates short-time RMS
level, smooths the level with attack and decay/release behaviour, looks up the
gain in the relevant row of the `18 x 121` table, converts that dB gain into a
linear multiplier, and applies it to the band signal.

The level trajectory described by openMHA can be summarized as:

```text
L_st = short-time RMS band level
L_a  = first-order smoothing of 20*log10(L_st) with tau_attack
L_in = max(L_a, first-order smoothing of L_a with tau_decay)
gain = table_lookup(L_in)
```

`gtmin=-10`, `gtstep=1`, and `log_interp=yes` define the table abscissa and
interpolation. The table has a row for every band/channel pair. The absolute
input calibration is part of the algorithm: if SigmaStudio sees dBFS while the
table expects dB SPL, its lookup index must include the measured microphone,
ADC, analogue-gain, and digital-headroom offsets.

## Mapping to SigmaStudio

### Preferred implementation

Use one calibrated RMS level detector and a gain-curve lookup per active band,
then apply the exact 121-point curve. Preserve negative high-level gains. Match
20 ms attack, 100 ms release, and 100 ms RMS integration, while checking how the
selected SigmaStudio block defines each time constant.

Do not assume that equally named controls are equivalent. Verify whether the
Sigma block is peak or RMS, feed-forward or feedback, whether timing smooths
level or gain, and whether its numerical time is a time constant, rise time, or
settling time. The final equivalence evidence must be measured steady-state
input/output curves and level-step responses.

### If only a conventional WDRC block is available

Use `sigma_compact_targets.csv` to initialize the block:

- crossover boundaries from `edge_low_hz` and `edge_high_hz`;
- the reported CAMFIT compression ratio;
- the gains at 45, 65, and 85 dB SPL as fitting checkpoints;
- the first input level that reaches 100 dB SPL as the limiter knee;
- 20/100/100 ms as attack/release/RMS targets.

This is a piecewise approximation. Quantify its deviation from the exact table
at every 1 dB input point instead of selecting the fit by eye.

### IIR crossover recommendation

For the first SigmaStudio implementation, a fourth-order Linkwitz–Riley
(`LR4`) crossover is a more defensible starting point than independent octave
band-pass filters because adjacent low-pass/high-pass paths are intended to
recombine flat and in phase at each crossover. Use the CEC1 boundaries above,
not generic octave frequencies.

However, a cascade of independent crossovers is not automatically equivalent
to the parallel FFT bank. Later splits add phase delay to some branches. Use a
native multiband crossover cell if available, or add phase/all-pass compensation
and verify all-pass-through reconstruction with every compressor at 0 dB.
Acceptance should include:

- summed magnitude ripple over the usable band;
- leakage between adjacent bands;
- phase/group delay and total latency;
- reconstruction error with all gains at unity;
- response after unequal static gains are applied to adjacent bands.

An LR4 implementation can be a documented Tiresias approximation; it must not
be described as a bit-exact reproduction of the openMHA FFT bank.

## Comparison protocol implications

### Electrical comparison

Use the configurations under `generated/openmha_cfg/one_mic_reference/`. They
bypass the adaptive differential microphone while retaining the same
prescription chain. The file interface still expects four channels, so duplicate
the mono test signal to front/rear left/right channels. This isolates the
fitting/compressor instead of adding directional-microphone processing to only
one side of the comparison.

The exact CEC1 reference runs at 44.1 kHz; Tiresias is expected to run at 48 kHz.
Keep the reference at 44.1 kHz and compare both systems on a common physical
frequency/level grid after calibrated resampling in the analysis. Changing the
openMHA configuration to 48 kHz is useful as a sensitivity experiment but is no
longer the unmodified CEC1 baseline.

At minimum, measure:

1. unity reconstruction of each implementation;
2. steady tones swept in frequency at several calibrated input SPL values;
3. input/output curves in every band, including the 100 dB SPL limit region;
4. attack and release with calibrated level steps;
5. broadband speech/noise transfer, latency, and artefacts.

### Electroacoustic comparison

Place the KH80 DSP and DUT at fixed geometry and calibrate free-field SPL at the
DUT microphone position. Record loudspeaker setting, distance, height, angle,
room, microphone sensitivity, preamplifier gain, interface gain, battery state,
and temperature.

Using an Earthworks microphone for openMHA but the board microphone for Tiresias
changes two things simultaneously: algorithm and input transducer. The result is
a useful end-to-end platform comparison, but not a clean test of the Sigma
implementation against openMHA. Add one of these controls:

- feed both algorithms from the same calibrated electrical microphone signal;
- measure the board-microphone transfer separately and compensate it in the
  analysis; or
- publish the electrical result as algorithm equivalence and label the
  electroacoustic result explicitly as end-to-end system performance.

Without an anthropomorphic ear or ear simulator, these are free-field tests;
they do not establish real-ear aided response or insertion gain.

## Exact versus approximate configurations

- `generated/openmha_cfg/cec1_exact/`: original CEC1 chain, including its
  adaptive differential microphone (`ADM`).
- `generated/openmha_cfg/one_mic_reference/`: same GHA chain with ADM bypassed,
  suitable for the proposed electrical and one-microphone comparisons.

The openMHA side should be called a **literature reference/baseline**, not a
metrological gold standard. The Tiresias result becomes directly attributable
to the implementation only after calibration and transducer controls are in
place.

## Decisions still needed before the campaign

1. Exact SigmaStudio compressor/crossover blocks available on ADAU1787 and their
   parameter semantics.
2. DSP instruction/RAM budget for 8 active WDRC bands plus one unity path.
3. Tiresias sample rate and all analogue/digital gain settings.
4. Mapping between dBFS at the ADAU1787 and dB SPL at the board microphone.
5. Electrical injection and capture points, impedances, and maximum safe levels.
6. Whether the comparison is mono, dual-mono, or truly binaural.
7. Whether the Earthworks signal can also be fed to the Tiresias algorithm as a
   control condition.
8. Input-level test grid and safe interpretation of the nominal 100 dB SPL MPO
   in an electrical bench setup.

## Source traceability

- Bisgaard audiograms: DOI `10.1177/1084713810379609`.
- CAMFIT/GHA implementation: pinned pyClarity commit recorded in
  `generated/generation_summary.json`.
- openMHA executable: version and commit recorded in
  [`../../tools/clarity/README.md`](../../tools/clarity/README.md).
- Generated content hashes: `generated/SHA256SUMS.txt`.
