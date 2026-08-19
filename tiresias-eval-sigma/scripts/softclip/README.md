# CEC1 output soft clip

These scripts program the `SoftClip` peak dynamics block directly. They avoid
manual manipulation of the SigmaStudio graph.

The addresses come from export commit `6286b03`, whose signal path is
`phasecomp -> output_headroom -> SoftClip -> SDSP OUT`:

- `output_headroom`: `0x285C`, expected to contain `-22 dB` during the
  campaign. The block is before `SoftClip` in the signal path;
- `SoftClip` table: `0x2860`, 45 four-byte 5.23 gain words;
- `SoftClip hold`: `0x2914`, expected to contain zero;
- `SoftClip decay`: `0x2918`, expected to contain the exported value
  `0x0000013D`;

The first table word is the underflow value for inputs below `-90 dBFS`.
Word 1 is `-90 dBFS`, word 2 is `-87 dBFS`, and subsequent words retain the
3 dB spacing. This convention follows the ADI compressor-table documentation;
the previous script incorrectly assigned `-90 dBFS` to word 0 and therefore
applied approximately one grid step too much attenuation.

`softclip_apply_cec1.sss` implements:

```text
y = x                                      x <= -27.036 dBFS
y = -27.036 + 0.2 * (x + 27.036)          -27.036 < x < -1.856 dBFS
y = -22                                    x >= -1.856 dBFS
```

where `x` is detector input level and `y` is output level. Each stored value is
the corresponding linear gain `10^((y - x) / 20)`, quantized to 5.23.

The `-22 dB` stage must precede the detector. It contains the `-20 dB`
conversion between the CEC1 input calibration (`0 dBFS = 100 dB SPL`) and
output calibration (`0 dBFS = 120 dB SPL`), plus 2 dB of campaign margin.
The threshold and ceiling above are shifted down by the same 2 dB, preserving
the openMHA transfer in relative-gain measurements.

## Operation

1. Stop the REW stimulus.
2. Run **Link Compile Download**.
3. If required, run `../campaign_apply_output_headroom.sss`.
4. Run `softclip_apply_cec1.sss` and require its `PASS` message. This
   underflow-aligned nominal table is the campaign candidate.
5. Load a prescription and perform the measurement.
6. Use `softclip_restore_transparent.sss` to disable the soft clip without a
   new compile/download.

Both scripts verify every table word by reading it back. The apply script also
checks the output headroom, hold and decay values before changing the table.

## Detector-coordinate calibration

Do not tune the CEC1 table against openMHA output measurements. If the block's
detector-index scale must be identified, follow
`../../rew/prescription-campaign-2026-08-14/SOFTCLIP_VALIDATION_PROTOCOL.md`.
The procedure uses `softclip_detector_identification.sss`, whose gain is
`-0.5 * index` dB, and the independent analyzer
`experiments/prescriptions/scripts/calibrate_sigma_softclip.py`.

The analyzer produces `softclip_apply_cec1_calibrated.sss` only when the
measured detector mapping is monotonic and spans both CEC1 knees.
openMHA output values are used only as a subsequent validation gate, never as
fit targets.

The calibrated table is retained as a diagnostic artifact, but it is not the
current campaign candidate. With N7 active at `-39.85 dBV`, the transparent
and identification outputs were `-18.82` and `-32.92 dBV`, respectively,
selecting word index `28.205`. The unity-sine detector calibration did not
remain invariant after the multiband prescription changed the signal crest
factor. The word-aligned nominal table avoids transferring that
waveform-dependent RMS-to-peak map between operating states.

The 3 dB table spacing and gain-table representation follow ADI's
"Compressor Table Format - Changing compressors at run-time" documentation:
https://ez.analog.com/dsp/sigmadsp/w/documents/5173/compressor-table-format---changing-compressors-at-run-time
