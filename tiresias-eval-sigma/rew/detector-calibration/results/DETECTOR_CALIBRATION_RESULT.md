# Resultado da calibração comum dos detectores B1–B8

## Condição de medição

A entrada da Focusrite Scarlett 18i8 foi ajustada e calibrada para **1 Vrms = 0 dBFS (full scale)**. O REW foi configurado para exibir a entrada diretamente em dBV sob essa condição.

O ensaio usou seno estacionário, leitura da componente espectral na frequência de cada banda e o ADAU1787 EVAL com a topologia SigmaStudio atual.

## Integridade

- Registros completos: 32/32.
- Erro máximo entre esta análise independente e os resultados armazenados na aba Analysis: 0.000000000 dB.
- Rastreamento unity médio (saída menos DAC do REW): -0.402 dB.
- Faixa do rastreamento unity: -0.420 a -0.380 dB.

## Mapa medido

| Banda | f (Hz) | detector @45 | @65 | @85 | @95 dB SPL | Diagnóstico |
|---:|---:|---:|---:|---:|---:|---|
| B1 | 177 | -40.16 | -35.14 | -17.14 | -7.18 | piso/contaminação em nível baixo |
| B2 | 297 | -59.57 | -39.63 | -19.90 | -9.79 | mapeamento aproximadamente linear |
| B3 | 500 | -59.90 | -40.08 | -20.20 | -10.25 | mapeamento aproximadamente linear |
| B4 | 841 | -59.91 | -40.15 | -20.27 | -10.26 | mapeamento aproximadamente linear |
| B5 | 1414 | -59.89 | -40.15 | -20.20 | -10.33 | mapeamento aproximadamente linear |
| B6 | 2378 | -59.79 | -40.15 | -20.18 | -10.16 | mapeamento aproximadamente linear |
| B7 | 4000 | -59.79 | -40.00 | -20.09 | -10.09 | mapeamento aproximadamente linear |
| B8 | 6727 | -59.30 | -39.29 | -19.57 | -9.40 | mapeamento aproximadamente linear |

## Interpretação

B2–B8 acompanham o nível aplicado de forma aproximadamente 1:1. A diferença entre detector e nível elétrico é pequena e específica por banda; por isso o mapa medido substitui a hipótese nominal única.

B1 não acompanha os dois níveis mais baixos: o detector fica próximo de −40 dBFS a 45 dB SPL equivalente e só converge para uma inclinação aproximadamente unitária nos níveis altos. Isso é compatível com um piso de energia de baixa frequência dentro da banda — por exemplo ruído, hum ou conteúdo residual — porque o detector RMS integra toda B1, embora a leitura do REW observe apenas a componente de 177 Hz.

Consequência: abaixo do primeiro ponto confiável, B1 não consegue distinguir níveis de entrada diferentes. A geração das prescrições deve manter o ganho de 45 dB SPL nessa região, e não extrapolar uma reta fictícia. B2–B8 podem usar interpolação por trechos e extrapolação pelas extremidades.

## Próxima validação recomendada

Antes de tratar o comportamento de B1 como propriedade definitiva do ADAU1787, medir o espectro interno/saída de B1 sem seno e verificar especialmente 50/60 Hz e seus harmônicos. A prescrição pode ser gerada e validada desde já com a política conservadora descrita acima.
