# Convergência temporal N1: sweeps de 1M e 2M

A comparação usa pares N1/unity independentes em cada duração. Cada curva de ganho foi resumida por mediana em uma janela total de 1/48 de oitava; a fase não foi usada.

| Nível | |2M−1M| mediano | percentil 95 | máximo entre 150 Hz e 9 kHz | máximo nos centros | decisão |
|---:|---:|---:|---:|---:|---|
| 45 dB SPL | 0.121 dB | 0.369 dB | 0.564 dB | 0.294 dB | inconclusivo por ruído de rede/SNR |
| 65 dB SPL | 0.019 dB | 0.130 dB | 0.253 dB | 0.232 dB | marginal: B6 = 0,232 dB |
| 85 dB SPL | 0.002 dB | 0.009 dB | 0.016 dB | 0.006 dB | PASS |

## Interpretação

- **85 dB SPL convergiu claramente:** a diferença máxima em toda a faixa útil foi 0,016 dB.
- **65 dB SPL é praticamente estável:** 95% da faixa ficou dentro de 0,130 dB. Somente B6 excedeu o critério de centro de ±0,20 dB, chegando a 0,232 dB; o excesso foi 0,032 dB.
- **45 dB SPL não permite atribuir as diferenças à dinâmica:** a contaminação já observada produz dispersão local e diferenças não monotônicas. O resultado é marcado como inconclusivo, não como falha do WDRC.
- Para a validação atual, 1M é suficiente em 65 e 85 dB SPL. Para uma curva quantitativa de referência em 45 dB SPL, repita em uma alimentação limpa ou use stepped sine com settling de 500 ms.
- Não foi aplicada correção matemática de attack/release; a conclusão vem diretamente da invariância observada ao dobrar a duração.
