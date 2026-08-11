# ADAU1787 power-supply spectrum comparison — 2026-08-07

This directory preserves and processes nine REW spectrum measurements: three
input conditions (`no input`, `-10 dBV`, and `-6 dBV`, with the tones at 1 kHz)
under three supply-source conditions (EVAL onboard regulators, Tiresias VDD,
and Tiresias AVDD).

The Tiresias-powered measurements were made from battery, with VBUS
disconnected. During acquisition the Tiresias firmware intentionally exercised
the platform by reading and writing flash, advertising continuously over BLE,
and blinking LEDs.

## Directory contents

- `raw/rew/`: the original REW `.mdat` files copied without modification.
- `raw/exports/`: the original full-resolution REW text exports.
- `processed/spectra_full_resolution.csv.gz`: tidy full-resolution data.
- `processed/spectra_1_24_octave.csv`: energy-mean 1/24-octave data used in the figures.
- `processed/summary.csv`: acquisition metadata and diagnostic metrics.
- `figures/`: comparison figures in editable SVG plus PNG and PDF.
- `setup/`: destination for the original setup photograph.
- `metadata.yaml`: experiment-level metadata and fields still requiring confirmation.
- `SHA256SUMS.txt`: SHA-256 manifest for every preserved raw file.

## Reproduce the processing

From the repository root:

```bash
python3 scripts/analysis/plot_rew_power_supply.py
```

The plotted 1/24-octave curves are an energy mean of the REW spectral bins,
used only to make differences readable. They are not integrated octave-band
levels. The unsmoothed values remain in the raw exports and the compressed
full-resolution table.

## Preliminary checks

- The applied 1 kHz tones are closely matched across supply conditions. Their
  peaks differ by no more than 0.007 dB within each input-level set.
- With no input, REW reports 22 Hz–22 kHz unweighted RMS values of −83.8 dBFS
  for Tiresias VDD, −83.5 dBFS for the EVAL regulators, and −82.0 dBFS for
  Tiresias AVDD.
- Relative to the EVAL, the median difference of the 1/24-octave no-input curve
  is −0.46 dB for Tiresias VDD and +1.99 dB for Tiresias AVDD over 20 Hz–22 kHz.
  In this acquisition, therefore, VDD is marginally lower in broadband noise
  than the EVAL reference, while AVDD is clearly higher. This ranking should be
  treated as a result of this run, not yet as a general conclusion.

## Interpretation boundary

These measurements compare complete powered configurations while a deliberately
active firmware workload was running. They do not, by themselves, isolate the
causal coupling path or prove that VSYS is the source of any observed spectral
component. Exact EVAL jumper configuration, injection point, audio routing,
firmware commit, and setup photo should be added before publication use.
