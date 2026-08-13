# Resultado da validação N1 a 4 kHz

## Condições

- Plataforma: ADAU1787 EVAL
- Perfil: CAMFIT N1
- Frequência: 4 kHz (centro de B7)
- Níveis equivalentes: 45, 65 e 85 dB SPL
- Saídas calibradas do DAC no REW: -59,85, -39,85 e -19,85 dBV
- Entrada da Focusrite Scarlett 18i8: 1 Vrms = 0 dBFS
- Comparação: magnitude da componente espectral de 4 kHz

## Resultado

| Nível equivalente | DAC | Unity | N1 | Ganho medido | Previsão recombinada | Erro |
|---:|---:|---:|---:|---:|---:|---:|
| 45 dB SPL | -59,85 dBV | -60,24 dBV | -44,42 dBV | +15,8200 dB | +16,0279 dB | -0,2079 dB |
| 65 dB SPL | -39,85 dBV | -40,25 dBV | -29,51 dBV | +10,7400 dB | +10,7159 dB | +0,0241 dB |
| 85 dB SPL | -19,85 dBV | -20,24 dBV | -12,68 dBV | +7,5600 dB | +7,5706 dB | -0,0106 dB |

A restauração foi verificada no ponto de 65 dB SPL: a saída voltou de
-29,51 dBV para -40,25 dBV, igual à referência unity, produzindo erro de
restauração de 0,0000 dB.

## Conclusão

**GO.** O script de aplicação reproduziu a previsão da saída recombinada nos
três níveis, com erro absoluto máximo de 0,2079 dB e erro absoluto médio de
0,0809 dB, ambos dentro do limite provisório de 0,50 dB. O script de
restauração retornou exatamente à referência unity no ponto verificado,
atendendo ao limite de 0,10 dB.

Os alvos corretos destas medidas são os ganhos recombinados. Os ganhos CAMFIT
isolados de B7 não são diretamente observáveis no REW porque a saída contém a
soma complexa das nove bandas do filterbank.
