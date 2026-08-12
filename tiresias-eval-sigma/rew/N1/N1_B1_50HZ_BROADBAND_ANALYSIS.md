# Analise das medidas RMS banda larga N1/B1

As medidas iniciais nao podem ser usadas diretamente como ganho do tom porque
a saida N1 contem ruido de outras bandas somado energeticamente a componente de
50 Hz.

Assumindo que a componente tonal recebe o ganho CAMFIT esperado, o ruido foi
estimado por:

```text
P_ruido = P_saida_N1 - P_tom_esperado
tom_esperado_dBV = saida_unity_dBV + ganho_CAMFIT_dB
```

| Entrada REW | Saida N1 banda larga | Tom esperado | Ruido inferido |
|---:|---:|---:|---:|
| -59,85 dBV | -49,36 dBV | -56,99 dBV | -50,18 dBV |
| -49,85 dBV | -46,68 dBV | -49,57 dBV | -49,81 dBV |
| -39,85 dBV | -39,77 dBV | -40,23 dBV | -49,75 dBV |

A consistencia do ruido inferido, aproximadamente -49,9 dBV, explica o ganho
aparente crescente nas entradas baixas. O resultado nao reprova a LUT; ele
mostra que RMS banda larga nao separa o tom do ruido amplificado pelas bandas
altas da prescricao.

Para validar o ganho B1, repetir o ensaio registrando a magnitude da componente
de 50 Hz no espectro do REW. As medidas banda larga devem ser preservadas para
a caracterizacao posterior do ruido de saida da prescricao.
