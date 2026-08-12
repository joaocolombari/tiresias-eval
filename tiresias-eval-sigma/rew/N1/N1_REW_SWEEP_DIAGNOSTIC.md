# Diagnóstico dos sweeps REW da prescrição N1

Foram analisados os três sweeps nomeados `−59,85 dBV`, `−49,85 dBV` e
`−39,85 dBV`. Os arquivos `.mdat` estão em `rew/N1`; os respectivos exports
de texto foram encontrados em `rew/bias`.

## Normalização

O eixo vertical exportado pelo REW inclui o ganho/calibração da cadeia de
medição. Portanto, o ganho de inserção foi calculado em relação à medida unity
`rew/bias/bias_0dB_after.txt`, compensando também a diferença entre o nível do
sweep N1 e o nível do sweep unity:

```text
ganho_N1(f) = medida_N1(f)
              - [medida_unity(f) + nivel_sweep_N1 - nivel_sweep_unity]
```

Os níveis registrados nos cabeçalhos dos arquivos são:

| Medida | Nível do sweep no cabeçalho REW |
|---:|---:|
| −59,85 dBV | −67,3 dBFS |
| −49,85 dBV | −57,3 dBFS |
| −39,85 dBV | −47,3 dBFS |
| Unity de referência | −17,4 dBFS |

## Verificação de B1 em 50 Hz

| Nível equivalente | Ganho no sweep | Ganho N1 esperado | Erro |
|---:|---:|---:|---:|
| 45 dB SPL | +2,08 dB | +1,988 dB | +0,09 dB |
| 55 dB SPL | +0,47 dB | +0,571 dB | −0,10 dB |
| 65 dB SPL | −0,04 dB | 0,000 dB | −0,04 dB |

O sweep reproduz o resultado do teste estacionário em 50 Hz e confirma a
correção aplicada a B1 nesse ponto.

## Comportamento global observado

- A amplificação de altas frequências diminui quando o nível de entrada sobe,
  comportamento qualitativamente coerente com a prescrição compressiva N1.
- Em 4 kHz, o ganho de inserção medido foi aproximadamente 16,98 dB, 14,58 dB
  e 11,71 dB para os três níveis, respectivamente.
- Em 6,727 kHz, os ganhos foram aproximadamente 18,00 dB, 13,67 dB e 9,52 dB.
- Aparecem elevações nas regiões de transição e ganho residual relevante acima
  do crossover de 8,724 kHz, embora B9 não possua compressor.

## Limitação do método

Um log sweep não mede uma função de transferência linear convencional quando
atravessa compressores independentes por banda. Em cada instante, as bandas
fora da frequência do sweep recebem apenas as caudas dos filtros. Seus
detectores podem interpretar esse sinal como nível muito baixo, selecionar
ganho elevado e tornar essas caudas audíveis na soma. Os tempos RMS e decay
também introduzem memória entre frequências sucessivas.

Assim, os sweeps são adequados para:

- verificar conectividade e estabilidade;
- observar qualitativamente a forma global e a dependência com o nível;
- detectar descontinuidades, saturação ou respostas claramente anômalas.

Eles não são suficientes para declarar correta a prescrição inteira nem para
comparar diretamente cada ponto da curva com o ganho CAMFIT da banda
correspondente. A validação quantitativa de B2 a B8 deve usar sinais
estacionários por banda, com tempo de estabilização definido, preferencialmente
ruído limitado em banda para reproduzir a variável RMS que alimenta cada
detector.

## Conclusão

As três curvas são internamente coerentes e confirmam B1 em 50 Hz. O resultado
global parece plausível para uma primeira implementação N1, mas também mostra
por que a calibração e validação dos detectores B2–B8 ainda são necessárias.
