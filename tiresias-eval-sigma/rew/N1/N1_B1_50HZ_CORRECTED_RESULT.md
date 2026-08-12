# Resultado da validação corrigida N1/B1 a 50 Hz

O teste confirma a implementação da LUT corrigida nos três pontos de validação.

| Nível equivalente | Unity | N1 corrigida | Ganho medido | Ganho esperado | Erro |
|---:|---:|---:|---:|---:|---:|
| 45 dB SPL | -60,18 dBV | -58,19 dBV | +1,99 dB | +1,988463 dB | +0,001537 dB |
| 55 dB SPL | -50,17 dBV | -49,66 dBV | +0,51 dB | +0,570642 dB | -0,060642 dB |
| 65 dB SPL | -40,18 dBV | -40,26 dBV | -0,08 dB | 0,000000 dB | -0,080000 dB |

## Tratamento dos dados

- Os valores `60.18` na condição unity de 45 dB SPL e `40.26` na condição N1 de 65 dB SPL foram interpretados como omissões do sinal negativo. Essa normalização é coerente com o nível comandado pelo REW e com as demais medições da série.
- O ganho foi calculado por `N1 corrigida - unity`.
- A restauração não foi repetida neste ensaio. Seu funcionamento é aceito com base no ensaio espectral anterior, no qual o erro de restauração ficou entre -0,01 e +0,02 dB. As células de restauração permanecem vazias para não registrar valores inferidos como se fossem novas medições.

## Conclusão

O erro absoluto máximo foi **0,08 dB**, e o erro absoluto médio foi **0,047 dB**. Para esta validação inicial de bancada, a prescrição N1/B1 corrigida é considerada aprovada nos três pontos medidos.

Esse resultado valida a escrita das LUTs, a fatoração do bias e a correção empírica do mapeamento do detector para B1. Ele ainda não valida a generalização para outras frequências, bandas, níveis intermediários ou sinais de banda larga.
