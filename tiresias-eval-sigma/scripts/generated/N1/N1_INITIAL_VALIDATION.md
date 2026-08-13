# N1: validação elétrica no ADAU1787 EVAL

## Escopo atual

Este ensaio valida a prescrição CAMFIT N1 nas oito LUTs ativas e nos três
estágios comuns de bias. Os scripts já usam a calibração compartilhada dos
detectores B1–B8 medida com seno estacionário.

A entrada da **Focusrite Scarlett 18i8** foi ajustada e calibrada para
**1 Vrms = 0 dBFS (full scale)**. O REW apresenta a entrada em dBV. Não mude o
ganho da Scarlett durante a campanha; uma mudança invalida o mapa elétrico.

O projeto permanece com `RMS TC = 20 ms`, `Hold = 0 ms` e
`Decay = 100 ms`. O ganho global CEC1 de −20 dB ainda não está implementado no
projeto SigmaStudio e não deve ser confundido com o ganho WDRC por banda.

## Arquivos autoritativos

- `N1_apply_prescription.sss`: carrega as oito LUTs e os três biases;
- `N1_restore_unity.sss`: restauração segura;
- `N1_validation_targets.csv`: detector medido, entrada elétrica e ganho CAMFIT
  para cada banda e nível;
- `N1_manifest.json`: curvas completas, endereços, palavras 5.23, condições de
  medição e hashes;
- `../../PRESCRIPTION_GENERATION_SUMMARY.csv`: resumo das dez prescrições.

## Procedimento

1. Desconecte fones e reduza a monitoração.
2. Execute **Link Compile Download** e confirme a resposta unity.
3. Selecione a frequência e o nível elétrico indicados em
   `N1_validation_targets.csv`.
4. Registre a componente espectral unity.
5. Execute `N1_apply_prescription.sss` e prossiga somente após `PASS`.
6. Repita exatamente os mesmos pontos sem alterar ganhos ou roteamento.
7. Execute `N1_restore_unity.sss`, exija `PASS` e confirme a restauração em pelo
   menos um nível baixo e um alto.

## Primeiro ponto de fumaça

Antes da varredura completa, valide um único ponto em **4 kHz**:

| Parâmetro | Valor |
|---|---:|
| Nível equivalente | 65 dB SPL |
| Saída do DAC no REW | −39,85 dBV |
| Detector previsto em B7 | −40,00 dBFS |
| Ganho CAMFIT isolado de B7 | +12,2367 dB |
| Ganho previsto na saída recombinada | **+10,7159 dB** |

Meça a componente de 4 kHz imediatamente depois de **Link Compile Download**,
carregue `N1_apply_prescription.sss` e meça novamente sem mudar nenhum controle.
O resultado observado no REW é `nível N1 − nível unity` e deve ser comparado a
**+10,7159 dB**. O valor de +12,2367 dB pertence apenas a B7 e não é diretamente
observável na saída, pois o REW mede a soma complexa das nove bandas.

Por fim, carregue `N1_restore_unity.sss` e repita a medida. Neste primeiro teste,
considere **GO provisório** se o script e o readback passarem, o ganho ficar a
até 0,50 dB da previsão recombinada e a restauração ficar a até 0,10 dB da
referência unity.

## Interpretação de B1

Em 177 Hz, B1 apresentou detector inferido de aproximadamente −40,16, −35,14,
−17,14 e −7,18 dBFS para 45, 65, 85 e 95 dB SPL equivalentes. Os dois primeiros
pontos revelam um piso/contaminação de baixa frequência. A LUT conserva o ganho
de 45 dB SPL abaixo do primeiro ponto, porque níveis menores não são
distinguíveis pelo detector nessa condição.

Isso permite validar a prescrição de forma conservadora, mas a origem do piso
de B1 deve ser caracterizada separadamente com uma medida sem seno, observando
50/60 Hz e harmônicos.

## Aceitação

- nenhum erro de escrita ou readback;
- restauração dentro de 0,10 dB da referência unity;
- ausência de clipping, instabilidade ou ruído inesperado;
- resultados arquivados com perfil, banda, frequência, nível, arquivo do
  projeto, commit e condição `Scarlett FS = 1 Vrms`;
- comparação final feita contra a previsão do sistema recombinado, não apenas
  contra o ganho isolado da banda-alvo nas regiões de crossover.

Em `N1_validation_targets.csv`, use `predicted_recombined_gain_db` como alvo da
medida no REW. As colunas `expected_camfit_gain_db` e
`predicted_target_band_gain_db` descrevem somente a banda indicada na linha.
