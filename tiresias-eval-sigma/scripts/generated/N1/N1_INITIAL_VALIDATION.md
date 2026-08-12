# N1: validacao eletrica inicial no EVAL-ADAU1787

## Escopo

Este ensaio valida a escrita da primeira prescricao CAMFIT completa nas oito
LUTs e nos tres estagios de bias. Ele ainda nao e a comparacao CEC1 completa:

- o ganho global de saida de -20 dB ainda nao existe no projeto Sigma;
- o offset eletrico do detector foi medido apenas para B1, com seno de 50 Hz;
- os offsets B2 a B8 para ruido limitado em banda ainda estao pendentes;
- a equivalencia temporal com o detector openMHA sera ensaiada separadamente.

Para a curva de ganho em regime permanente, o projeto permanece com
`RMS TC = 20 ms`, `Hold = 0 ms` e `Decay = 100 ms`.

## Mapeamento eletrico nominal

A calibracao medida foi:

```text
detector_B1_dBFS = entrada_eletrica_dBV + 4,85 dB
nivel_CEC1_dB_SPL = detector_B1_dBFS + 100 dB
```

Portanto, os niveis eletricos de ensaio continuam sendo:

```text
entrada_eletrica_dBV = nivel_CEC1_dB_SPL - 104,85 dB
```

O primeiro ensaio mostrou que essa equacao nao descreve a abscissa interna do
detector nos niveis baixos. A calibracao espectral posterior mediu:

| Entrada no EVAL | Detector B1 inferido |
|---:|---:|
| -59,85 dBV | -40,04 dBFS |
| -49,85 dBV | -38,20 dBFS |
| -39,85 dBV | -32,68 dBFS |

O `N1_apply_prescription.sss` atual foi regenerado para atingir os tres ganhos
CAMFIT nesses niveis reais do detector. Este ajuste e uma validacao inicial de
tres pontos, nao uma caracterizacao completa abaixo de 45 dB SPL.

## Pontos iniciais em 50 Hz

| Nivel CEC1 equivalente | Entrada no EVAL | Ganho N1/B1 esperado |
|---:|---:|---:|
| 45 dB SPL | -59,85 dBV | +1,988463 dB |
| 55 dB SPL | -49,85 dBV | +0,570642 dB |
| 65 dB SPL | -39,85 dBV | 0,000000 dB |
| 75 dB SPL | -29,85 dBV | 0,000000 dB |
| 85 dB SPL | -19,85 dBV | 0,000000 dB |

Use diretamente o nivel indicado no DAC calibrado do REW. Este ensaio e uma
comparacao relativa entre unity, N1 e restauracao; nao e necessario medir de
novo a entrada do EVAL. Aguarde pelo menos 1 s em cada nivel antes de registrar
a saida.

## Procedimento

Registre os resultados em
[`../../../rew/N1/N1_B1_50HZ_CORRECTED_VALIDATION.csv`](../../../rew/N1/N1_B1_50HZ_CORRECTED_VALIDATION.csv).
As colunas calculadas podem permanecer vazias.

1. Desconecte fones e reduza a monitoracao.
2. Execute **Link Compile Download**.
3. Com seno de 50 Hz, mande o DAC gerar os niveis da tabela e meca a saida
   unity logo depois de **Link Compile Download**.
4. Execute `N1_apply_prescription.sss` e prossiga apenas se aparecer `PASS`.
5. Repita exatamente os mesmos niveis, sem mudar os ganhos da interface.
6. Calcule `ganho_N1 = saida_N1_dBV - saida_unity_dBV` para cada ponto.
7. Execute `N1_restore_unity.sss` e exija `PASS`.
8. Repita pelo menos os pontos de 45 e 65 dB SPL para confirmar a restauracao.

## Aceitacao inicial

- erro absoluto do ganho B1 em cada ponto: no maximo 0,25 dB;
- diferenca apos restauracao: no maximo 0,10 dB;
- nenhum erro de readback;
- nenhum clipping, instabilidade ou ruido inesperado.

Se o ponto de -59,85 dBV estiver limitado pelo piso de ruido, preserve o
resultado, aumente o numero de medias e nao altere o ganho da interface entre
unity, N1 e restauracao.

## Arquivos

- `N1_apply_prescription.sss`: carrega e verifica as oito LUTs e os tres biases;
- `N1_restore_unity.sss`: restauracao segura;
- `N1_validation_targets.csv`: alvos para todas as bandas;
- `N1_manifest.json`: mapeamento, enderecos, coeficientes e hashes das fontes.
