# Resultado da validação N1/B8 a 6727 Hz

## Condições

- Plataforma: ADAU1787 EVAL
- Perfil: CAMFIT N1
- Frequência: 6727 Hz (centro de B8)
- Níveis equivalentes: 45, 65 e 85 dB SPL
- Saídas calibradas do DAC no REW: -59,85, -39,85 e -19,85 dBV
- Entrada da Focusrite Scarlett 18i8: 1 Vrms = 0 dBFS
- Comparação: magnitude da componente espectral de 6727 Hz

## Resultado

| Nível equivalente | DAC | Unity | N1 | Ganho medido | Previsão recombinada | Erro |
|---:|---:|---:|---:|---:|---:|---:|
| 45 dB SPL | -59,85 dBV | -60,27 dBV | -44,04 dBV | +16,2300 dB | +16,2086 dB | +0,0214 dB |
| 65 dB SPL | -39,85 dBV | -40,26 dBV | -32,30 dBV | +7,9600 dB | +7,9424 dB | +0,0176 dB |
| 85 dB SPL | -19,85 dBV | -20,26 dBV | -16,16 dBV | +4,1000 dB | +4,1151 dB | -0,0151 dB |

## Conclusão

**GO.** O erro absoluto máximo foi 0,0214 dB e o erro absoluto médio foi
0,0181 dB, muito abaixo do limite provisório de 0,50 dB. Os resultados também
confirmam a previsão da soma complexa na região em que B8 se recombina com B9,
que não atravessa os três estágios comuns de bias.
