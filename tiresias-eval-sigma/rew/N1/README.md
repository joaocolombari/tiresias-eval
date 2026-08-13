# Medicao inicial N1/B1 a 50 Hz

> **Resultado mais recente:** a prescrição N1 a 4 kHz foi aprovada em 45, 65 e
> 85 dB SPL equivalentes. Consulte `N1_4KHZ_SMOKE_RESULT.md`: erro absoluto
> máximo de ganho 0,2079 dB, erro absoluto médio 0,0809 dB e restauração com
> erro 0,0000 dB no ponto verificado.

> **Banda alta:** B8 a 6727 Hz também foi aprovada nos mesmos três níveis.
> Consulte `N1_B8_6727HZ_RESULT.md`: erro absoluto máximo 0,0214 dB e erro
> absoluto médio 0,0181 dB.

> **Região média:** B6 a 2378 Hz teve erro máximo de 0,5911 dB. Consulte
> `N1_B6_2378HZ_RESULT.md`. A continuação da campanha passa a usar as curvas
> automáticas descritas em `N1_REW_CURVE_PROTOCOL.md`, mantendo B6–B8 como
> âncoras estacionárias para validar o sweep.

> **Histórico:** este diretório preserva a validação inicial específica de B1.
> A campanha reutilizável B1–B8 para N1–N10 está em
> `rew/detector-calibration/README.md`. Para os próximos ensaios, siga o README
> comum, não este protocolo antigo.

Preencha `N1_B1_50HZ_MEASUREMENTS.csv` sem alterar os nomes das colunas.

1. Aplique pelo DAC calibrado do REW o valor indicado em
   `rew_dac_output_dbv` e, logo depois de **Link Compile Download**, anote a
   saida em `unity_output_dbv`.
2. Carregue `N1_apply_prescription.sss` sem alterar nenhum ganho do setup e anote a
   saida em `n1_output_dbv`.
3. Depois de `N1_restore_unity.sss`, anote a saida em
   `restored_output_dbv`.
4. As colunas calculadas podem ficar vazias; o processamento preencherá:

```text
measured_gain_db    = n1_output_dbv - unity_output_dbv
gain_error_db       = measured_gain_db - expected_gain_db
restoration_error_db = restored_output_dbv - unity_output_dbv
```

Nao e necessario medir novamente a entrada do EVAL neste teste relativo: a
calibracao existente do DAC define o nivel aplicado. Use ponto como separador
decimal e preserve uma linha por nivel.

## Medida espectral de 50 Hz

A primeira execucao com RMS banda larga revelou um piso de ruido N1 proximo de
-49,9 dBV, que domina os pontos baixos. Preserve esses valores em
`N1_B1_50HZ_MEASUREMENTS.csv`.

Para validar o ganho do compressor, use
`N1_B1_50HZ_SPECTRAL_MEASUREMENTS.csv` e registre somente a magnitude da
componente de 50 Hz no espectro do REW, nos estados unity, N1 e restaurado. Use
a mesma janela, tamanho de FFT, medias e roteamento nas tres condicoes.

O primeiro resultado espectral mostrou que o offset do detector medido em
niveis altos nao pode ser extrapolado para os niveis baixos. A recalibracao usa
`N1_B1_DETECTOR_SPECTRAL_CALIBRATION.csv` e o script
`../../scripts/b1_detector_spectral_calibration.sss`. Restaure com
`../../scripts/b1_detector_spectral_restore_unity.sss`.

Depois da calibracao, o gerador atualizou `N1_apply_prescription.sss` para os
tres niveis reais do detector. Registre a repeticao separadamente em
`N1_B1_50HZ_CORRECTED_VALIDATION.csv`, preservando os dois ensaios anteriores.
