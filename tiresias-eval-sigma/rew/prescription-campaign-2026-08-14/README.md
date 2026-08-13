# Campanha elétrica das dez prescrições — 14/08/2026

Este diretório está pronto para medir `N1`–`N7` e `S1`–`S3` no
EVAL-ADAU1787Z e comparar, para 45, 65 e 85 dB SPL equivalentes:

- ganho medido no SigmaDSP, calculado como `prescrição - unity`;
- resposta estacionária prevista a partir das LUTs quantizadas, dos mapas
  medidos dos detectores e da recombinação complexa do banco LR4;
- referência CEC1 `one_mic_reference` executada no openMHA 4.17.0.

A referência openMHA preserva a calibração de saída e o **soft clip** da cadeia
CEC1. Isso é deliberado: representa o baseline completo da literatura. Como o
Sigma atual não tem esse estágio de limitação, o relatório separa
`medido–modelo Sigma`, `medido–openMHA` e `modelo Sigma–openMHA`; assim uma
diferença causada pela arquitetura, especialmente nos perfis severos, não será
confundida com erro de carregamento das LUTs.

São **33 medições**: três referências unity comuns e três curvas para cada um
dos dez perfis. A lista e os nomes exatos estão em
`CAMPAIGN_MEASUREMENT_MANIFEST.csv`.

## Condição que não pode mudar

- Scarlett 18i8: entrada calibrada para **1 Vrms = 0 dBFS**, exibida em dBV.
- Ganho físico, cabos, canal, roteamento e calibração do REW: iguais durante
  toda a campanha.
- EVAL-ADAU1787Z e projeto `tiresias-eval.dspproj`.
- Compressores: RMS TC 20 ms, hold 0 ms e decay 100 ms.
- REW: 100 Hz–10 kHz, 48 kHz, 1M, um sweep, sem timing reference, start delay
  de 2 s e sem smoothing.
- Níveis enviados pelo DAC do REW: −59,85, −39,85 e −19,85 dBV, equivalentes
  a 45, 65 e 85 dB SPL no mapeamento usado pela prescrição.

Preencha os campos `TODO` em
`../../config/prescription_campaign_2026-08-14.json` antes de começar.

Da raiz do repositório, a checagem somente-leitura deve terminar em `PASS`:

```bash
tools/clarity/.venv/bin/python \
  experiments/prescriptions/scripts/check_prescription_campaign.py
```

Antes da aquisição ela deve informar 33 exports REW ainda ausentes; depois da
aquisição, zero.

## Atenuação obrigatória de saída

Antes de qualquer curva, execute **Link Compile Download** e depois
`../../scripts/campaign_apply_output_headroom.sss`. Prossiga somente com
`PASS`.

O script grava `DAC_VOL0 = DAC_VOL1 = 0x75`, isto é, −19,875 dB. A atenuação
é necessária porque prescrições severas podem produzir mais de 0 dBV sem ela.
O pior caso previsto da campanha fica em −7,392 dBV depois da atenuação,
preservando 7,392 dB até o full scale de 1 Vrms da Scarlett. Os 30 casos estão
em `CAMPAIGN_HEADROOM_AUDIT.csv` e todos devem estar como `PASS`.

Essa atenuação deve estar ativa tanto nas curvas unity quanto nas curvas com
prescrição. Portanto ela cancela exatamente na subtração `prescrição - unity`
e não altera o ganho estimado.

**Atenção:** cada novo **Link Compile Download** retorna os volumes dos DACs
ao valor salvo no projeto. Se precisar recompilar ou reiniciar, execute de novo
`campaign_apply_output_headroom.sss` antes de medir.

## Sequência de bancada

1. Faça o checklist em `GO_NO_GO_CHECKLIST.md`.
2. Com o projeto em unity e a atenuação de saída confirmada, meça as três
   referências na ordem 45, 65 e 85 dB SPL. Salve `.mdat` e exporte `.txt` nos
   caminhos da primeira parte do manifesto.
3. Para cada perfil, na ordem `N1`, `N2`, `N3`, `N4`, `N5`, `N6`, `N7`, `S1`,
   `S2`, `S3`:
   1. execute `../../scripts/generated/<perfil>/<perfil>_apply_prescription.sss`;
   2. prossiga somente se a janela mostrar `PASS`;
   3. meça 45, 65 e 85 dB SPL nessa ordem, usando os nomes exatos do manifesto;
   4. execute `../../scripts/generated/<perfil>/<perfil>_restore_unity.sss`;
   5. prossiga somente se a restauração mostrar `PASS`.
4. Ao final, execute `../../scripts/campaign_restore_output_headroom.sss` para
   devolver `DAC_VOL0/1` a 0 dB.

O start delay de 2 s deixa o estado do compressor decair antes de cada sweep.
Não altere a ordem dos níveis: mantê-la idêntica em todos os perfis reduz uma
fonte de variação sistemática.

## Se houver falha

- `ABORT`, `ERROR` ou ausência de `PASS`: não meça esse estado.
- Faça **Link Compile Download**, reaplique a atenuação de saída e repita o
  perfil desde o começo.
- Antes de reutilizar as três referências unity, confira em 1 kHz e
  −39,85 dBV que o nível voltou ao valor inicial dentro de 0,10 dB. Se não
  voltou, refaça as três curvas unity.
- Qualquer aviso de clipping no REW é `NO-GO`: preserve a captura, registre no
  manifesto e interrompa a sequência.

## Arquivos a salvar

Para cada linha do manifesto:

- use `rew_measurement_name` como nome da medição no REW;
- salve o `.mdat` em `mdat_path`;
- exporte magnitude e fase, sem smoothing, para `text_path`;
- marque `acquired`, `script_pass`, `clip_warning` e `notes` no próprio CSV.

Não renomeie os `.txt`: o analisador exige os nomes exatos para impedir que uma
curva seja atribuída ao perfil ou nível errado.

## Processamento depois das medições

Na raiz do repositório, execute:

```bash
tools/clarity/.venv/bin/python \
  experiments/prescriptions/scripts/analyze_prescription_campaign.py
```

O analisador valida os 33 arquivos, calcula `prescrição - unity`, compara com
o modelo Sigma e com o openMHA, e produz:

- `processed/sigma_measured_curves.csv`;
- `processed/comparison_metrics.csv`;
- `processed/rew_export_integrity.csv`;
- `figures/<perfil>_comparison.svg`;
- `reports/CAMPAIGN_RESULT.md`.

Os 14.430 pontos da previsão Sigma já estão em `expected/sigma/`. Os 4.830
pontos medidos automaticamente no openMHA já estão em `expected/openmha/`.
O nível de 45 dB SPL só será tratado quantitativamente se a aquisição no novo
laboratório apresentar relação sinal/ruído adequada; 65 e 85 dB SPL são os
níveis quantitativos definidos a priori.
