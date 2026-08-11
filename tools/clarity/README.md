# Local pyClarity installation

- Source: `https://github.com/claritychallenge/clarity`
- Pinned commit: `9df6486fb0bddc7619b3b99f1b3a5c72c109a3ec`
- Python: 3.11
- Local virtual environment: `.venv/` (ignored by Git)
- Local source checkout: `source/` (ignored by Git)
- pyClarity is installed editable from `source/` with only the dependencies
  required by the CAMFIT/GHA prescription and openMHA configuration path.
- Installed openMHA: 4.17.0 (`444d2cba8866`), executable `/usr/local/bin/mha`.

## Recreate the local environment

From the repository root, using Python 3.11:

```bash
python3.11 -m venv tools/clarity/.venv
git clone https://github.com/claritychallenge/clarity tools/clarity/source
git -C tools/clarity/source checkout 9df6486fb0bddc7619b3b99f1b3a5c72c109a3ec
tools/clarity/.venv/bin/python -m pip install \
  -r tools/clarity/requirements-prescriptions.lock
tools/clarity/.venv/bin/python -m pip install --no-deps -e tools/clarity/source
```

The prescription generator does not require the full Clarity machine-learning
stack. The smoke test additionally requires an openMHA executable. The tested
installation is openMHA 4.17.0 (`444d2cba8866`) at `/usr/local/bin/mha`.

Activate the environment with:

```bash
source tools/clarity/.venv/bin/activate
```

Regenerate the prescriptions with:

```bash
tools/clarity/.venv/bin/python \
  experiments/prescriptions/scripts/generate_camfit_prescriptions.py
```

The full pyClarity dependency set includes machine-learning packages such as
PyTorch. They were intentionally not installed because they are not imported by
the CEC1 CAMFIT/GHA prescription path and would not affect the generated gain
tables. The minimal environment is recorded in `requirements-prescriptions.lock`.

The pinned source checkout and virtual environment are intentionally not
versioned. Scripts, exact dependency versions, generated prescriptions and the
Clarity commit hash are versioned.
