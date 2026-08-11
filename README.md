# Tiresias Evaluation

Repositório de apoio à campanha de debug, caracterização e avaliação
experimental da plataforma de aparelhos auditivos Tiresias.

Este repositório mantém protocolos, evidências, dados, scripts de análise e
resultados reproduzíveis. Os projetos de produção de hardware e firmware são
mantidos separadamente e os diretórios locais `HW/` e `FW/` são
intencionalmente ignorados pelo Git.

## Destaque: prescrições Bisgaard/CAMFIT no openMHA

O pipeline em [`experiments/prescriptions`](experiments/prescriptions/README.md)
gera prescrições compressivas CAMFIT para os dez audiogramas padrão de
Bisgaard (`N1`–`N7` e `S1`–`S3`) usando a implementação do pyClarity e a cadeia
de referência CEC1 do openMHA.

Para cada perfil são produzidos:

- uma matriz de ganho `18 x 121`: nove bandas, dois ouvidos e níveis de entrada
  de -10 a 110 dB SPL;
- configurações openMHA com a cadeia CEC1 original e com o microfone
  diferencial em bypass;
- uma tabela completa e uma representação compacta para implementação e
  validação no SigmaStudio/ADAU1787;
- resultados de smoke test executados para os dez perfis.

Os tempos do compressor não são saídas do audiograma. Na referência CEC1 eles
são parâmetros fixos: ataque de 20 ms, release de 100 ms e integração RMS de
100 ms. O documento do experimento também descreve o banco FFT original, a
aproximação proposta com crossovers Linkwitz–Riley e os controles necessários
para as comparações elétrica e eletroacústica.

Comece por:

- [metodologia, entradas, saídas e mapeamento para o SigmaStudio](experiments/prescriptions/README.md);
- [tabela completa de prescrições](experiments/prescriptions/generated/gain_table_long.csv);
- [alvos compactos para o SigmaStudio](experiments/prescriptions/generated/sigma_compact_targets.csv);
- [pontos x/y para o gráfico do compressor](experiments/prescriptions/generated/sigma_compressor_curve_ui.csv);
- [protocolo de deslocamento de nível por banda](experiments/prescriptions/BAND_LEVEL_OFFSET_PROTOCOL.md);
- [instalação reproduzível do pyClarity](tools/clarity/README.md).

## Estrutura

```text
docs/
  debug/                 Hipóteses, análises e evidências de debug
  literature/            Datasheets, manuais e publicações de referência
  measurements/          Campanhas de medição com dados brutos e processados
experiments/
  prescriptions/         Bisgaard + CAMFIT + openMHA + alvos para SigmaStudio
scripts/
  analysis/              Processamento e geração reproduzível de resultados
tools/
  clarity/               Ambiente, versões e instruções de dependências
HW/                      Projeto local de hardware; ignorado pelo Git
FW/                      Projeto local de firmware; ignorado pelo Git
```

## Campanhas disponíveis

### Prescrições e comparação openMHA/Tiresias

Consulte [`experiments/prescriptions/README.md`](experiments/prescriptions/README.md).
O pipeline separa explicitamente:

- a prescrição CAMFIT;
- os parâmetros fixos do compressor;
- a implementação exata no openMHA;
- a aproximação destinada ao SigmaStudio;
- a comparação elétrica do algoritmo;
- a comparação eletroacústica end-to-end.

### Alimentação do ADAU1787

[`docs/measurements/adau1787_power_supply_2026-08-07`](docs/measurements/adau1787_power_supply_2026-08-07/README.md)
preserva nove medições REW e compara o espectro do ADAU1787 usando os
reguladores da EVAL, o VDD do Tiresias e o AVDD do Tiresias.

### Sequenciamento e falhas do ADAU1787

[`docs/debug/power-sequencing`](docs/debug/power-sequencing) reúne a análise de
sequenciamento, o risco dos GPIOs/SPORT e o material preparado para o
EngineerZone da Analog Devices.

## Reprodução rápida

Depois de preparar o ambiente conforme
[`tools/clarity/README.md`](tools/clarity/README.md):

```bash
tools/clarity/.venv/bin/python \
  experiments/prescriptions/scripts/generate_camfit_prescriptions.py

tools/clarity/.venv/bin/python \
  experiments/prescriptions/scripts/run_openmha_smoke_test.py --profile N3
```

Para regenerar as figuras da campanha de alimentação:

```bash
python3 scripts/analysis/plot_rew_power_supply.py
```

## Política de dados e rastreabilidade

- dados brutos organizados sob `docs/measurements/` não devem ser sobrescritos;
- resultados derivados devem ser regeneráveis por scripts versionados;
- arquivos `SHA256SUMS.txt` registram a integridade dos dados e prescrições;
- versão de hardware, firmware, commits, calibração e setup devem ser registrados
  antes de qualquer resultado ser usado em publicação;
- resultados de debug e resultados científicos devem permanecer claramente
  separados.
