# Per-band level offset: openMHA FFT versus Tiresias LR4

## Purpose

The CEC1 compressor selects gain from the RMS level measured inside each
rectangular FFT band. The Tiresias implementation measures RMS after an LR4
crossover branch. These filters have different shapes and equivalent noise
bandwidths, so the same broadband signal does not necessarily produce the same
detector level in both implementations.

This protocol estimates one steady-state correction per band. It corrects the
average level presented to the gain curve; it does not make an overlapping LR4
bank mathematically identical to a nonoverlapping rectangular FFT bank.

## Sign convention

For the same input waveform, measure:

```text
r_ref,b   = openMHA/reference band RMS in dBFS
r_sigma,b = Sigma LR4 branch RMS in dBFS
delta_b   = r_ref,b - r_sigma,b
```

Interpretation:

- positive `delta_b`: the LR4 branch reads too low;
- negative `delta_b`: the LR4 branch reads too high;
- corrected reference level: `x_ref,b = x_sigma,b + delta_b`.

For a prescription point at band level `L` in dB SPL, with CEC1 input
peaklevel `C_in = 100 dB SPL`, enter the horizontally shifted Sigma point:

```text
x_graph,b = L - C_in - delta_b
y_graph,b = x_graph,b + G_b(L)
```

Keep the CAMFIT gain `G_b(L)` inside the compressor. For the electrical CEC1
comparison, apply the `-20 dB` input/output headroom difference once after all
bands are recombined. This also attenuates the ninth, unity boundary band.

## Stimulus

Use deterministic, zero-mean Gaussian noise with:

- sample rate recorded in the run metadata;
- 20 s useful duration plus 0.5 s raised-cosine fades;
- at least five independent seeds;
- RMS level near -30 dBFS before band limiting;
- no normalization performed separately after each analysis filter;
- no A, C, or other perceptual weighting.

Generate one stimulus for each CEC1 band, limited by its exact edge
frequencies. Start with spectrally flat noise inside each band. Repeat the
measurement with speech-shaped noise as a validation, because the fitted
offset is an average weighted by the stimulus spectrum.

## Measurement configuration

1. Bypass every compressor or set every curve to unity.
2. Disable the final `-20 dB` headroom gain during branch-level measurement.
3. Keep ADC, DAC and any measurement-interface gains fixed.
4. Route only one LR4 branch at a time to the measurement output.
5. All-pass phase compensation may remain enabled because its ideal magnitude
   is unity, but verify that it does not change measured RMS.
6. Discard the first 2 s of every capture so filter and RMS transients do not
   affect the estimate.
7. Use the identical waveform and analysis interval for the reference and LR4
   measurements.

A digital loop or exported branch signal is preferred. If an analogue capture
is required, compute every result relative to a simultaneously measured or
separately repeated full-band bypass capture. This cancels constant ADC/DAC and
interface gain.

## Reference measurement

The reference path must implement the CEC1 rectangular bands using the same
edges listed in `config/camfit_cec1.json`. Suitable methods are:

1. capture the corresponding internal openMHA FFT-band signal; or
2. apply an offline frequency-domain rectangular mask to the exact stimulus
   and calculate its RMS over the same time interval.

The second method is sufficient for the level-offset experiment because the
reference bands are rectangular and nonoverlapping.

## LR4 measurement

For every stimulus band and seed:

1. play the band-limited waveform through the unity Tiresias/Sigma path;
2. capture the output of the matching LR4 branch before compression;
3. calculate RMS in the steady-state interval;
4. record `r_sigma,b` and `r_ref,b` in
   `data/sigma_band_offset_measurements.csv`;
5. calculate `delta_b = r_ref,b - r_sigma,b`.

Do not use a single tone to obtain this offset. A tone only measures the gain at
one frequency; noise integrates the complete passband and therefore includes
the equivalent-noise-bandwidth difference that drives an RMS compressor.

## Aggregation and acceptance

For each band, report the mean offset across seeds and its sample standard
deviation. Use the mean as the initial horizontal curve shift only when:

- standard deviation is at most 0.10 dB;
- no capture clips;
- changing the input by 10 dB changes both measured branch levels by
  `10.00 +/- 0.10 dB`;
- the offset measured with speech-shaped noise differs from the flat-noise
  result by no more than 0.5 dB.

If the last criterion fails, retain both results and use the speech-shaped
offset for the hearing-aid comparison. The difference is evidence that one
scalar offset cannot fully compensate the different filter shapes.

## Final validation

After shifting the compressor curves, verify the complete steady-state
input/output map with band-limited noise at several levels, including the
CAMFIT knee and limiting region. Compare the measured digital gain with the
121-point reference table. Recommended acceptance is:

- maximum steady-state gain error at checkpoints: 0.5 dB;
- RMS error over all tested levels: 0.25 dB;
- no ADC, internal DSP, recombination, or DAC clipping.

