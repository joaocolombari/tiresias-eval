# Calibração comum dos detectores B1–B8

Esta calibração pertence ao EVAL, ao banco de filtros e aos blocos RMS — não a uma prescrição. Execute-a uma vez e reutilize o resultado em N1–N10.

## Procedimento por banda

1. Execute **Link Compile Download**. Todas as LUTs e os três biases devem estar em unity.
2. Gere o seno estacionário na frequência indicada na planilha e meça a componente espectral unity nos quatro níveis.
3. Rode `B<n>_detector_identification.sss` uma única vez.
4. Repita os quatro níveis, aguardando pelo menos 2 s após cada mudança.
5. Rode `detector_identification_restore_all_unity.sss` antes da próxima banda.

Preencha somente as colunas amarelas da planilha `rew/detector-calibration/ADAU1787_EVAL_detector_calibration.xlsx`. Não use sweep.
