# Calibracao eletrica do detector RMS de B1

## Objetivo

Medir a relacao real entre a tensao de entrada em dBV e o nivel usado para
indexar a LUT do compressor. Isso inclui a faixa do ADC, a convencao RMS do
algoritmo e a resposta do ramo LR4.

O projeto exportado configura AIN0 como entrada de linha, PGA desligado e ganho
digital do ADC em 0 dB. O datasheet do ADAU1787 especifica 0.49 V rms como
entrada analogica nominal de 0 dBFS, equivalente a -6.196 dBV. Esse valor e uma
previsao inicial; o resultado medido e a referencia para os scripts CAMFIT.

## Estimulo

- senoide de 50 Hz;
- valores RMS em dBV;
- pelo menos 1 s de estabilizacao antes de registrar a saida;
- mesma entrada, roteamento e medicao nos estados unitario e de calibracao;
- iniciar no menor nivel e subir;
- interromper se houver clipping ou comportamento inesperado.

O tom de 50 Hz deixa a contribuicao das bandas acima de B1 desprezivel. Este
ensaio identifica a escala do detector; os offsets de energia entre o banco FFT
e o LR4 continuam sendo medidos separadamente com ruido limitado em banda.

## Procedimento

1. Desligar SelfBoot ou garantir que o projeto correto ja foi baixado.
2. Executar Link Compile Download.
3. Com B1 unitario, medir a saida para cada entrada listada em
   `b1_detector_calibration.csv` e preencher `unity_output_dbv`.
4. Executar `../../scripts/b1_detector_calibration.sss` e exigir a mensagem PASS.
5. Repetir os mesmos niveis e preencher `calibration_output_dbv`.
6. Executar `../../scripts/b1_detector_restore_unity.sss` e exigir PASS.
7. Repetir pelo menos um ponto para confirmar o retorno ao estado inicial.

## Calculo

Para cada linha:

```text
measured_gain_change_db = calibration_output_dbv - unity_output_dbv
inferred_detector_dbfs = -2 * (measured_gain_change_db + 27)
detector_minus_input_dbv = inferred_detector_dbfs - input_dbv
```

A LUT foi construida com:

```text
gain_db = -0.5 * detector_dbfs - 27
```

O offset final deve ser estimado pela media das linhas que estejam claramente
acima do ruido e abaixo de clipping. Se a dispersao exceder 0.2 dB, nao gerar as
prescricoes ainda: revisar o nivel do gerador, a leitura RMS, a estabilizacao e
o roteamento.

Com a Scarlett calibrada para 1 V rms de full scale, os valores exibidos pelo
REW podem ser registrados diretamente em dBV. Aumentar o ganho analogico da
entrada da Scarlett melhora a relacao sinal/ruido da captura, desde que esse
ganho e a calibracao permanecam inalterados entre as medidas unitaria e de
calibracao.

Os pontos unitarios inicialmente registrados mostram aproximadamente -0.40 dB
de ganho do caminho entre -46.2 e -10.2 dBV. O ponto de -66.2 dBV esta afetado
pelo piso de ruido e deve ser excluido da estimativa final; -56.2 dBV deve ser
tratado inicialmente como ponto de verificacao.

## Resultado de 12 de agosto de 2026

As colunas derivadas de `b1_detector_calibration.csv` foram calculadas a partir
das medidas originais. A ultima medida, -34.91 dBV, foi movida da coluna de
ganho para `calibration_output_dbv`, onde se encaixa na sequencia registrada.

O caminho unitario entre -46.2 e -10.2 dBV apresentou inclinacao de 0.99910
dB/dB e residuo maximo de 0.0163 dB. Para a conversao inicial do detector foram
usados os dois pontos mais altos, ainda abaixo de clipping:

```text
detector_minus_input = 4.85 dB
desvio padrao amostral = 0.099 dB
detector_dBFS = input_dBV + 4.85 dB
```

Os demais pontos permanecem no CSV como evidencia do vies crescente quando a
saida medida se aproxima do piso de ruido. O resultado estruturado esta em
`b1_detector_calibration_summary.json`.

## Proxima etapa

Depois desse offset, os 34 pontos de cada compressor correspondem a niveis de
entrada conhecidos. As curvas CAMFIT podem entao ser amostradas em TAB0/TAB1
(-90 dBFS), TAB2 (-87 dBFS), ate TAB33 (+6 dBFS), incorporando o offset medido
por banda.
