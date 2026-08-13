# Validação das curvas N1 de 1M no REW

As seis curvas foram usadas somente para validar o método. A condição de 45 dB SPL equivalente apresenta contaminação de rede/SNR visivelmente maior e não deve ser usada para caracterizar o ruído próprio da plataforma.

A curva medida foi calculada por `N1 - unity` em dB e resumida com mediana em uma janela total de 1/48 de oitava. A fase foi ignorada.

## Comparação com os tons estacionários

| Nível | desvio máximo | desvio médio | interpretação |
|---:|---:|---:|---|
| 45 dB SPL | 0.443 dB | 0.178 dB | contaminado; apenas validação qualitativa |
| 65 dB SPL | 0.092 dB | 0.033 dB | válido para magnitude |
| 85 dB SPL | 0.600 dB | 0.203 dB | válido para magnitude |

Os dados completos por centro de banda estão em `N1_1M_centre_validation.csv`. Os pontos pretos da figura são as medidas estacionárias B6–B8.

## Comparação global com o modelo (150 Hz a 9 kHz)

| Nível | erro mediano | percentil 95 | erro máximo |
|---:|---:|---:|---:|
| 45 dB SPL | 0.130 dB | 0.847 dB | 1.236 dB |
| 65 dB SPL | 0.020 dB | 0.353 dB | 0.558 dB |
| 85 dB SPL | 0.005 dB | 0.045 dB | 0.099 dB |

## Decisão

- **65 e 85 dB SPL: GO para validação de magnitude.**
- **45 dB SPL: GO apenas qualitativo.** Use a mediana local e preserve a marcação de contaminação; não use esta aquisição para piso de ruído, THD ou conclusões finas.
- Em 85 dB SPL, 95% da faixa ficou a menos de 0,046 dB do modelo; em 65 dB SPL, a mesma estatística foi 0,353 dB.
- A curva de 1M reproduz B7 e B8. Em B6/85 dB SPL, o sweep coincide com o modelo e sugere que o ponto estacionário anterior de +6,18 dB merece repetição futura.
- A convergência temporal 1M/2M foi executada posteriormente; consulte `N1_1M_2M_CONVERGENCE.md`.
