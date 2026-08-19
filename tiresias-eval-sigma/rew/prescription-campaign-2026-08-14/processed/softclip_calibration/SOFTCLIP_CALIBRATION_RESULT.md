# SigmaDSP SoftClip detector calibration

- Complete points: 11
- Included after transparent-path QC: 10
- Excluded: 1
- Median transparent loop delta: -0.410 dB
- Detector range: -51.219 to -1.219 dBFS peak
- LUT resampling: monotonic piecewise-linear measured detector map
- Linear-fit diagnostic only: R² = 0.972508171
- The fit uses only transparent/identification measurements; openMHA output is not an optimization target.

## Excluded raw rows

- Source -54.85 dBV: transparent -52.26 dBV; transparent path differs from the session median by 3.000 dB.

Generated script: `tiresias-eval-sigma/scripts/softclip/softclip_apply_cec1_calibrated.sss`
