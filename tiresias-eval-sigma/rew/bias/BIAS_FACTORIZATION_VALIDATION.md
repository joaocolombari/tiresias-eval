# Validacao da fatoracao LUT + bias

Data da medicao: 12/08/2026 18:10, conforme cabecalho do REW.

## Configuracao ensaiada

- LUTs dos compressores B1 a B8: -12 dB em todos os 34 pontos;
- `phasecomp.Gain1`, `Gain1_2` e `Gain1_3`: +4 dB cada;
- ganho liquido teorico de B1 a B8: 0 dB;
- B9: caminho direto, sem bias;
- estimulo REW: swept sine de 512k, um sweep a -17,4 dBFS;
- smoothing: nenhum;
- timing reference: nenhum.

## Resultado quantitativo

As comparacoes usam os 54.559 bins coincidentes entre 20 Hz e 20 kHz.

| Comparacao | Media (dB) | RMS (dB) | P95 absoluto (dB) | Maximo absoluto (dB) |
|---|---:|---:|---:|---:|
| Compensado - referencia anterior | +0,000334 | 0,008429 | 0,017 | 0,070 |
| Restaurado - referencia anterior | +0,000817 | 0,008256 | 0,017 | 0,062 |
| Compensado - restaurado | -0,000483 | 0,008546 | 0,018 | 0,052 |

Como o REW foi usado sem referencia temporal, a diferenca de fase foi
desenrolada e sua componente linear com a frequencia foi removida antes de
avaliar o residuo.

| Comparacao | Deslocamento temporal ajustado (us) | Desvio-padrao residual (graus) | P95 absoluto residual (graus) | Maximo absoluto residual (graus) |
|---|---:|---:|---:|---:|
| Compensado - referencia anterior | -0,0552 | 0,0554 | 0,1129 | 0,4219 |
| Restaurado - referencia anterior | -0,0134 | 0,0540 | 0,1107 | 0,4635 |

## Conclusao

**PASS.** A configuracao compensada e indistinguivel do estado unity dentro da
repetibilidade observada entre as duas medidas unity. Nao ha evidencia de erro
de magnitude, alteracao de fase ou descontinuidade na transicao para B9 causada
pela fatoracao.

Isso valida a arquitetura em que um bias comum e subtraido das LUTs B1 a B8 e
reposto pelos tres ganhos em cascata antes de `Add8`, enquanto B9 entra
diretamente no somador final.

## Integridade dos arquivos-fonte

| Arquivo | SHA-256 |
|---|---|
| `bias_0dB_before.txt` | `8c3942c36cecdac55eb29f6d2c445ba348b184c21480a389e3b397932f6f9390` |
| `bias_compensated.txt` | `7e342ad9c3083f5a0f0f3ab96065153df59d0200c62178a735c8bf61616e953f` |
| `bias_0dB_after.txt` | `1908b9a2ee116a4da6cb96915a6917bd8cc9508f1c8a6d2c1179479ffa9d5750` |
