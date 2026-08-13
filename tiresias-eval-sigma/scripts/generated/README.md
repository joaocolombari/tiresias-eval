# Prescrições SigmaStudio geradas

Este diretório contém as prescrições CAMFIT para os dez audiogramas-padrão de
Bisgaard: N1–N7 e S1–S3.

As LUTs foram geradas com a calibração elétrica comum B1–B8 do ADAU1787 EVAL.
Durante essa calibração, a entrada da **Focusrite Scarlett 18i8** estava
ajustada e calibrada para **1 Vrms = 0 dBFS (full scale)**, com o REW exibindo
dBV. Essa condição deve ser mantida durante a validação.

Cada diretório de perfil contém:

- `<perfil>_apply_prescription.sss`;
- `<perfil>_restore_unity.sss`;
- `<perfil>_validation_targets.csv`;
- `<perfil>_manifest.json`;
- `SHA256SUMS.txt`.

`PRESCRIPTION_GENERATION_SUMMARY.csv` resume o maior ganho prescrito, a
fatoração do bias e o hash da calibração usada em cada perfil.

Como o bloco usa uma grade de detector de 3 dB e interpola em ganho linear, o
gerador ajusta os nós 5.23 aos checkpoints de 45, 55, 65, 75, 85 e 95 dB SPL.
Após quantização, o maior erro previsto de ganho da banda-alvo entre todos os
dez perfis é inferior a **0,00027 dB**. Esse valor valida a representação da
LUT; a resposta total medida ainda inclui a recombinação das bandas LR4.

Para regenerar tudo a partir do diretório raiz:

```bash
python3 experiments/prescriptions/scripts/generate_sigma_adau1787_prescription.py \
  --all-profiles
```

Antes de aplicar uma prescrição, execute **Link Compile Download**. Prossiga
somente após a mensagem `PASS` do script. Entre perfis, use o script de
restauração e confirme novamente a resposta unity.

B1 tem uma limitação conhecida: o detector apresentou um piso em nível baixo.
A LUT mantém o ganho equivalente a 45 dB SPL abaixo do primeiro ponto medido.
Essa política é conservadora e está registrada nos manifestos; a origem do
piso deve ser investigada separadamente.
