# Go/no-go — campanha de prescrições

## Antes de energizar e medir

- [ ] Laboratório, computador, versões, seriais e cabeamento registrados no JSON da campanha.
- [ ] Scarlett ajustada e calibrada para **1 Vrms = 0 dBFS**; ganho físico travado.
- [ ] Saída de monitoração baixa e fones desconectados durante escritas de parâmetros.
- [ ] REW em 48 kHz, 100 Hz–10 kHz, 1M, um sweep, start delay 2 s, sem timing reference.
- [ ] Projeto `tiresias-eval.dspproj` aberto no SigmaStudio 4.7.
- [ ] **Link Compile Download** concluído sem erro.
- [ ] `campaign_apply_output_headroom.sss` retornou `PASS`.
- [ ] `CAMPAIGN_HEADROOM_AUDIT.csv`: 30 linhas em `PASS`.
- [ ] Resposta unity plana e sem clipping.

## Referências unity

- [ ] `unity_45dBSPL_-59p85dBV`
- [ ] `unity_65dBSPL_-39p85dBV`
- [ ] `unity_85dBSPL_-19p85dBV`
- [ ] Os três `.mdat` e `.txt` foram salvos nos caminhos do manifesto.

## Perfis

Para cada linha, confirme `PASS` na aplicação, as três aquisições, `PASS` na
restauração e ausência de clipping.

| Perfil | Apply | 45 dB | 65 dB | 85 dB | Restore | Sem clip |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| N1 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| N2 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| N3 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| N4 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| N5 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| N6 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| N7 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| S1 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| S2 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |
| S3 | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] |

## Fechamento

- [ ] Os 33 `.txt` e os 33 `.mdat` existem nos caminhos do manifesto.
- [ ] Todos os campos de execução do manifesto foram preenchidos.
- [ ] `campaign_restore_output_headroom.sss` retornou `PASS`.
- [ ] Projeto, REW e dados brutos foram fechados sem sobrescrever arquivos.
- [ ] O analisador terminou sem arquivos ausentes ou avisos de integridade.

Qualquer `ABORT`, `ERROR`, clipping, mudança de ganho/calibração ou resposta
unity que não retorne em ±0,10 dB é **NO-GO** para continuar sem registrar e
corrigir a condição.
