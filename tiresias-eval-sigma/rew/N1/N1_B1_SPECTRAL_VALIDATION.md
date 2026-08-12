# Resultado espectral N1/B1 a 50 Hz

## Resultado

| Nivel equivalente | Ganho medido | Ganho esperado | Erro | Restauracao |
|---:|---:|---:|---:|---:|
| 45 dB SPL | +0,05 dB | +1,988 dB | -1,938 dB | +0,02 dB |
| 55 dB SPL | +0,01 dB | +0,571 dB | -0,561 dB | 0,00 dB |
| 65 dB SPL | 0,00 dB | 0,000 dB | 0,000 dB | -0,01 dB |

## Decisao

**NO-GO para o mapeamento nominal de nivel nos dois pontos baixos.**

A restauracao dentro de 0,02 dB e o ponto de 65 dB SPL confirmam o caminho de
escrita/restauracao. O erro e dependente do nivel e aparece onde a curva N1
deveria fornecer ganho positivo. Isso aponta para a abscissa real do detector
RMS nos niveis baixos, nao para quantizacao 5.23 ou falha do bias.

A proxima etapa e medir o nivel do detector usando a propria componente
espectral de 50 Hz. O mapeamento anterior de +4,85 dB foi estimado nos niveis
altos; extrapola-lo para perto do piso do detector nao e valido.
