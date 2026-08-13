# Resultado da validação N1/B6 a 2378 Hz

## Condições

- Plataforma: ADAU1787 EVAL
- Perfil: CAMFIT N1
- Frequência: 2378 Hz (centro de B6)
- Níveis equivalentes: 45, 65 e 85 dB SPL
- Saídas calibradas do DAC no REW: -59,85, -39,85 e -19,85 dBV
- Entrada da Focusrite Scarlett 18i8: 1 Vrms = 0 dBFS
- Comparação: magnitude da componente espectral de 2378 Hz

## Resultado

| Nível equivalente | DAC | Unity | N1 | Ganho medido | Previsão recombinada | Erro |
|---:|---:|---:|---:|---:|---:|---:|
| 45 dB SPL | -59,85 dBV | -60,24 dBV | -52,45 dBV | +7,7900 dB | +8,0552 dB | -0,2652 dB |
| 65 dB SPL | -39,85 dBV | -40,24 dBV | -33,41 dBV | +6,8300 dB | +6,9733 dB | -0,1433 dB |
| 85 dB SPL | -19,85 dBV | -20,24 dBV | -14,06 dBV | +6,1800 dB | +5,5889 dB | +0,5911 dB |

## Conclusão

**GO provisório.** Os pontos de 45 e 65 dB SPL ficaram dentro do limite inicial
de 0,50 dB. O ponto de 85 dB SPL excedeu esse limite em apenas 0,0911 dB, com
erro total de +0,5911 dB. O comportamento é estável e monotônico, mas essa
diferença deve ser preservada e comparada à curva automática antes de concluir
se vem do modelo de recombinação, da dinâmica do detector ou da medida.

O erro absoluto máximo foi 0,5911 dB e o erro absoluto médio foi 0,3332 dB.

## Verificação posterior com sweep

O sweep de 1M em 85 dB SPL produziu +5,5805 dB em uma mediana local de 1/48 de
oitava, apenas -0,0084 dB em relação à previsão de +5,5889 dB. B7 e B8 também
coincidiram com os respectivos tons estacionários. Isso indica que o valor
estacionário de +6,18 dB em B6/85 dB SPL deve ser repetido antes de ser usado
como referência quantitativa; ele permanece preservado neste arquivo.
