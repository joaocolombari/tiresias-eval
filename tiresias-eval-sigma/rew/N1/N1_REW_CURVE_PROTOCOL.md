# Protocolo de curvas automáticas N1 no REW

## Objetivo

Substituir a repetição manual em todas as bandas por seis curvas automáticas:
três níveis em unity e os mesmos três níveis com N1. Os pontos estacionários já
medidos em B6, B7 e B8 servem como âncoras para validar o método de sweep.

Como o WDRC é não linear e possui memória (`RMS TC = 20 ms`, `Decay = 100 ms`),
estas curvas representam uma resposta quase estacionária dependente de nível.
Use magnitude e ganho relativo; não interprete a resposta impulsiva ou a fase
como caracterização de um sistema LTI.

## Configuração do Measure

| Parâmetro | Valor |
|---|---:|
| Tipo | SPL / logarithmic measurement sweep |
| Faixa solicitada | 100 Hz a 10 kHz |
| Sample rate | 48 kHz |
| Length | 1M |
| Repetitions | 1 |
| Start delay | 2 s |
| Níveis | -59,85; -39,85; -19,85 dBV |
| Entrada Scarlett | 1 Vrms = 0 dBFS |

Não altere volume, ganho, roteamento, cabos ou calibração entre as seis curvas.
Um sweep único e longo é preferido a várias repetições curtas. Verifique que a
saída e a entrada não clipam, especialmente com N1 ativa.

### Relação entre sweep e dinâmica do WDRC

Em 48 kHz, `1M` corresponde a aproximadamente 21,85 s de sinal. Para a faixa
solicitada de 100 Hz a 10 kHz, o REW excita aproximadamente 50 Hz a 20 kHz e o
sweep atravessa cerca de 8,64 oitavas. Isso resulta em aproximadamente
2,53 s/oitava. Durante os 100 ms de decay, a frequência muda apenas cerca de
0,040 oitava, pequena em relação ao espaçamento aproximado de 0,75 oitava entre
os centros das bandas deste filterbank.

Por isso, `1M` é o ponto de partida recomendado. `256k` dura aproximadamente
5,46 s e muda cerca de 0,16 oitava durante 100 ms, tornando a influência da
dinâmica bem mais provável nas regiões de crossover.

Esses cálculos não eliminam a necessidade de validação: o sistema é não linear
e não há correção posterior simples para attack/release. A influência temporal
deve ser limitada e quantificada por convergência.

## Teste de convergência temporal

Antes das seis curvas definitivas, use o nível intermediário de -39,85 dBV:

1. Meça unity com `1M`.
2. Aplique N1 e meça com `1M`.
3. Restaure unity e meça com `2M`.
4. Aplique N1 novamente e meça com `2M`.
5. Calcule as curvas de ganho `N1_1M / unity_1M` e
   `N1_2M / unity_2M`.
6. Compare as duas entre 150 Hz e 9 kHz, especialmente nos centros e
   crossovers.

Considere `1M` convergido se `N1_2M - N1_1M` permanecer dentro de ±0,20 dB nos
centros das bandas e dentro de ±0,50 dB em toda a faixa útil. Se não convergir,
use `2M` nas curvas definitivas ou migre para stepped sine.

Não se aplica uma compensação matemática de attack/release aos resultados. A
análise deve declarar duração, direção e velocidade do sweep, mostrar o teste
de convergência e comparar as curvas com os tons estacionários já medidos.

## Aquisição

1. Execute `N1_restore_unity.sss` e confirme `PASS`.
2. Meça e salve:
   - `unity_45dBSPL_-59p85dBV`;
   - `unity_65dBSPL_-39p85dBV`;
   - `unity_85dBSPL_-19p85dBV`.
3. Execute `N1_apply_prescription.sss` e confirme `PASS`.
4. Repita sem mudar nenhum parâmetro e salve:
   - `N1_45dBSPL_-59p85dBV`;
   - `N1_65dBSPL_-39p85dBV`;
   - `N1_85dBSPL_-19p85dBV`.
5. Salve a sessão em um único arquivo `.mdat` dentro de `rew/N1/curves/`.

## Curvas de ganho

No `Trace Arithmetic`, calcule uma razão N1/unity para cada nível, equivalente
a subtrair as magnitudes em dB:

- `N1_45dBSPL / unity_45dBSPL`;
- `N1_65dBSPL / unity_65dBSPL`;
- `N1_85dBSPL / unity_85dBSPL`.

Não subtraia uma única curva unity dos três níveis. Manter os pares preserva
eventuais diferenças dependentes do nível na cadeia de medição.

## Validação do sweep contra os tons estacionários

Compare as curvas de ganho nos centros já medidos:

| Frequência | 45 dB SPL | 65 dB SPL | 85 dB SPL |
|---:|---:|---:|---:|
| 2378 Hz | +7,79 dB | +6,83 dB | +6,18 dB |
| 4000 Hz | +15,82 dB | +10,74 dB | +7,56 dB |
| 6727 Hz | +16,23 dB | +7,96 dB | +4,10 dB |

O sweep é aceito como método de caracterização da magnitude se reproduzir os
pontos estacionários com desvio de até 0,50 dB. Se o desvio for sistemático ou
dependente da direção/frequência, use o `Stepped Sine` do RTA com pelo menos
300 ms de settling por frequência; 500 ms é o valor conservador recomendado
para esta primeira campanha. Com a hipótese conservadora de uma dinâmica de
primeira ordem, 500 ms correspondem a cinco vezes o decay configurado de
100 ms e deixam menos de 1% do transitório inicial.

## Arquivamento

Preserve o `.mdat` original e exporte as seis respostas e as três razões em
texto. Registre versão do REW, projeto SigmaStudio, commit, data, operador e
confirmação de que a Scarlett permaneceu em `1 Vrms = 0 dBFS`.
