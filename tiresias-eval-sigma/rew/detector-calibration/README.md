# Calibração comum dos detectores do ADAU1787 EVAL

Esta campanha calibra uma única vez os detectores RMS das bandas B1–B8 do
projeto SigmaStudio atual. O resultado pertence ao conjunto **EVAL + ADC +
banco de filtros + blocos RMS** e será reutilizado na geração de N1–N10.

Use a planilha `ADAU1787_EVAL_detector_calibration.xlsx` e preencha somente as
colunas amarelas da aba `Measurements`.

## Condição da interface de aquisição

A entrada da **Focusrite Scarlett 18i8** está ajustada e calibrada para
**1 Vrms = 0 dBFS (full scale)**. O scope do REW foi calibrado para apresentar
diretamente o valor em dBV nessa condição. Esta configuração faz parte da
calibração: qualquer alteração no ganho da entrada da Scarlett invalida o mapa
elétrico obtido aqui e exige uma nova campanha B1–B8.

## Procedimento

Para cada banda, na ordem B1 até B8:

1. Execute **Link Compile Download**. Todas as LUTs B1–B8 e os três biases
   devem estar em unity.
2. Configure no REW o seno estacionário na frequência indicada na planilha.
3. Meça somente a componente espectral dessa frequência nos níveis de
   `−59,85`, `−39,85`, `−19,85` e `−9,85 dBV`. Registre em
   `unity_component_dbv`.
4. Execute uma vez o script
   `scripts/generated/detector-identification/B<n>_detector_identification.sss`.
5. Repita os quatro níveis, aguardando pelo menos 2 s após cada mudança, e
   registre em `identification_component_dbv`.
6. Execute
   `scripts/generated/detector-identification/detector_identification_restore_all_unity.sss`
   antes de iniciar a próxima banda. Um novo **Link Compile Download** também
   restaura unity.

## Frequências

| Banda | Frequência |
|---:|---:|
| B1 | 177 Hz |
| B2 | 297 Hz |
| B3 | 500 Hz |
| B4 | 841 Hz |
| B5 | 1414 Hz |
| B6 | 2378 Hz |
| B7 | 4000 Hz |
| B8 | 6727 Hz |

Não use sweep para preencher a planilha. Os valores devem ser obtidos com seno
estacionário e pela magnitude da componente espectral indicada.

Depois de preencher e salvar a planilha, a análise calcula o nível interno dos
oito detectores. Esses dados serão gravados em
`config/detector_calibration_eval.json`; em seguida, os geradores produzirão as
LUTs das dez prescrições usando a mesma calibração.

Execute a análise com:

```bash
python3 experiments/prescriptions/scripts/analyze_sigma_detector_calibration.py
```

Os resultados derivados são salvos em `results/`; as medidas originais da aba
`Measurements` não são alteradas.
