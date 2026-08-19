# CEC1 output soft clip

These scripts program the `SoftClip` peak dynamics block directly. They avoid
manual manipulation of the SigmaStudio graph.

The addresses come from the export with `SoftClip` before `output_headroom`:

- `SoftClip` table: `0x285C`, 45 four-byte 5.23 gain words;
- `SoftClip hold`: `0x2910`, expected to contain zero;
- `SoftClip decay`: `0x2914`, expected to contain the exported value
  `0x0000013D`;
- `output_headroom`: `0x2924`, expected to contain `-22 dB` during the
  campaign. The block is after `SoftClip` in the signal path.

The table maps detector levels from `-90` through `+42 dBFS` in 3 dB steps.
The first 39 words cover the graph's visible `-90` through `+24 dBFS` range;
the final six words continue the curve above the visible range.

`softclip_apply_cec1.sss` implements:

```text
y = x                                      x <= -27.036 dBFS
y = -27.036 + 0.2 * (x + 27.036)          -27.036 < x < -1.856 dBFS
y = -22                                    x >= -1.856 dBFS
```

where `x` is detector input level and `y` is output level. Each stored value is
the corresponding linear gain `10^((y - x) / 20)`, quantized to 5.23.

## Operation

1. Stop the REW stimulus.
2. Run **Link Compile Download**.
3. If required, run `../campaign_apply_output_headroom.sss`.
4. Run `softclip_apply_cec1.sss` and require its `PASS` message.
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

The 3 dB table spacing and gain-table representation follow ADI's
"Compressor Table Format - Changing compressors at run-time" documentation:
https://ez.analog.com/dsp/sigmadsp/w/documents/5173/compressor-table-format---changing-compressors-at-run-time
