# Protocolo de validação do SoftClip CEC1 — 19/08/2026

## Estado antes da calibração

O teste estacionário N7 em 1 kHz confirmou operação, repetibilidade e
restauração do bloco, mas não equivalência quantitativa completa:

| Nível equivalente | Entrada REW | Unity | N7 transparente | N7 + SoftClip | Ganho medido | Ganho openMHA | Erro |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 45 dB SPL | -59,85 dBV | -82,23 dBV | -22,19 dBV | -38,73 dBV | 43,50 dB | 49,26 dB | -5,76 dB |
| 65 dB SPL | -39,85 dBV | -62,23 dBV | -18,82 dBV | -36,10 dBV | 26,13 dB | 29,26 dB | -3,13 dB |
| 85 dB SPL | -19,85 dBV | -42,23 dBV | -16,97 dBV | -34,77 dBV | 7,46 dB | 8,92 dB | -1,46 dB |

A regressão entre saída transparente e saída limitada apresenta inclinação
`0,761`, embora a curva nominal programada tenha inclinação `0,2`. Isso indica
que a correspondência entre nível detectado e índice da LUT não é a escala que
foi inicialmente assumida. Não se deve ajustar a LUT diretamente contra os
resultados do openMHA: isso seria circular.

## Princípio da correção

A calibração abaixo identifica independentemente a coordenada do detector. A
LUT de identificação grava ganho `-0,5 × índice` dB. Assim, para cada tom:

```text
índice fracionário = -2 × (saída_identificação - saída_transparente)
```

O ajuste usa somente níveis elétricos do SigmaDSP. Depois dele, a mesma equação
CEC1 é reamostrada nas coordenadas medidas do ADAU1787. Nenhum ponto do openMHA
é usado para otimizar a LUT.

## Fase A — identificação do detector

Condição: EVAL-ADAU1787Z, Scarlett sem ganho, `9,74727 Vrms = 0 dBFS`, seno
contínuo de 1 kHz, leitura RMS em dBV, sem smoothing.

1. Faça **Link Compile Download**.
2. Execute `N7_restore_unity.sss` ou confirme todos os compressores de banda em
   unity.
3. Execute `softclip_restore_transparent.sss`.
4. Execute `campaign_restore_output_headroom.sss`: a calibração do detector é
   feita temporariamente com `output_headroom = 0 dB`.
5. Em ordem crescente, aplique `-59,85`, `-54,85`, ..., `-9,85 dBV`. Espere
   **1,0 s** após cada mudança e preencha `transparent_output_dbv` em
   `raw/softclip/softclip_detector_calibration.csv`.
6. Pare o tom e execute `softclip_detector_identification.sss`; prossiga apenas
   com `PASS`.
7. Repita os mesmos onze níveis, na mesma ordem, e preencha
   `identification_output_dbv`. No primeiro nível, espere 2 s; nos demais, 1 s.
8. Pare o tom e execute `softclip_restore_transparent.sss`.
9. Execute novamente `campaign_apply_output_headroom.sss` para retornar a
   `-22 dB`.

Critérios antes de gerar a LUT:

- pelo menos oito pares completos;
- atenuação de identificação negativa e monotônica;
- faixa medida cobrindo os dois joelhos da curva;
- regressão índice × nível com `R² ≥ 0,995`.

Geração, na raiz do repositório:

```bash
python experiments/prescriptions/scripts/calibrate_sigma_softclip.py
```

O resultado será `scripts/softclip/softclip_apply_cec1_calibrated.sss`, além do
CSV da LUT, JSON de metadados e relatório do ajuste.

## Fase B — gate estacionário independente

1. Faça **Link Compile Download**.
2. Execute `campaign_apply_output_headroom.sss`.
3. Execute `N7_apply_prescription.sss`.
4. Execute `softclip_apply_cec1_calibrated.sss`.
5. Com seno de 1 kHz, meça em ordem crescente `-59,85`, `-39,85` e
   `-19,85 dBV`, esperando 1 s em cada ponto.
6. Restaure N7 e repita unity no primeiro e no último nível para verificar
   deriva.

Targets openMHA em 1 kHz, calculados antes da nova calibração:

| Nível | Ganho target | Saída target usando o unity medido |
|---:|---:|---:|
| 45 dB SPL | 49,2606 dB | -32,9694 dBV |
| 65 dB SPL | 29,2593 dB | -32,9707 dBV |
| 85 dB SPL | 8,9242 dB | -33,3058 dBV |

**GO:** erro absoluto `≤ 2,0 dB` nos três níveis, saída monotônica, ausência de
clipping e unity antes/depois dentro de `0,10 dB`. Se falhar, não ajustar a LUT
contra esses três targets: registrar a diferença como limitação arquitetural.

## Fase C — campanha das dez prescrições

Somente depois do GO:

1. Mantenha `output_headroom = -22 dB` e a LUT calibrada durante toda a sessão.
2. Refaça as três referências unity.
3. Para N1–N7 e S1–S3, carregue a prescrição, exija `PASS` e meça 45, 65 e
   85 dB SPL equivalentes, sempre em ordem crescente.
4. Use exatamente 100 Hz–10 kHz, 48 kHz, 1M, um sweep, start delay de 2 s e sem
   smoothing, preservando `.mdat` e exportando `.txt`.
5. Repita N7/1 kHz estacionário no meio e no fim da campanha como controle.

O sweep REW e os tons estacionários respondem de forma diferente por causa do
estado do detector de pico. A análise final deve apresentar duas comparações:

- **primária, like-for-like:** o mesmo sweep processado pelo openMHA e pelo
  ADAU1787, preservando ataque/release;
- **secundária, canônica:** tons estacionários openMHA após acomodação de 0,5 s.

Isso evita favorecer qualquer plataforma e permite separar fidelidade da
prescrição, dinâmica do soft clip e efeito do método de medida.
