# Resultado da calibracao espectral do detector B1

A LUT de identificacao implementou:

```text
ganho_dB = -0,25 * detector_dBFS - 10
detector_dBFS = -4 * (ganho_medido_dB + 10)
```

| Entrada REW | Ganho da LUT de identificacao | Detector inferido | Detector - entrada |
|---:|---:|---:|---:|
| -59,85 dBV | +0,01 dB | -40,04 dBFS | +19,81 dB |
| -49,85 dBV | -0,45 dB | -38,20 dBFS | +11,65 dB |
| -39,85 dBV | -1,83 dB | -32,68 dBFS | +7,17 dB |

O detector nao segue um offset constante nos niveis baixos. A aproximacao de
+4,85 dB obtida em niveis altos nao pode ser extrapolada. Em particular, com
entrada de -59,85 dBV o detector ja indica aproximadamente -40 dBFS.

Isso explica por que a N1 nominal selecionou a regiao de ganho aproximadamente
nulo em vez dos ganhos CAMFIT de +1,99 e +0,57 dB.

A restauracao ficou entre -0,01 e +0,02 dB. A escrita da LUT de identificacao e
a inversao da curva sao consideradas validas para esta etapa.
