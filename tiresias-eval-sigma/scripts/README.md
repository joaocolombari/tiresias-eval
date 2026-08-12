# Smoke test da LUT do compressor B1

Este ensaio verifica, no EVAL-ADAU1787 e sem alterar o projeto de produção, se o
SigmaStudio consegue escrever e ler de volta a tabela do compressor
`compbank.Compressor-B1`.

O teste altera somente os 34 coeficientes da LUT de B1:

- endereço inicial: `0x212C`;
- tamanho: 136 bytes (34 palavras de 32 bits);
- estado inicial/restaurado: `0x00800000` = ganho 1,0 = 0 dB;
- estado de teste: `0x004026E7` = ganho 0,501187205 = -6,00000049 dB.

Os endereços acima foram obtidos do `HexArray` exportado pelo SigmaStudio. Não
use os endereços individuais `TABn_ADDR` do cabeçalho `*_PARAM.h`: eles não
representam corretamente o passo de quatro bytes entre palavras para este teste.

Para as chamadas de registrador, o nome amigável usado é `IC 1`, correspondente
ao componente físico ligado ao USBi no **Hardware Configuration**. O nome
`IC 1-Sigma`, presente nos arquivos exportados, identifica o núcleo SigmaDSP e não
deve ser passado como nome do IC para essa API.

## Segurança e preparação

1. Use somente o EVAL-ADAU1787 conectado pelo USBi.
2. Deixe fones desconectados e reduza o ganho de monitoração antes da escrita.
   A escrita direta da RAM de parâmetros pode produzir um transitório audível.
3. Abra `tiresias-eval.dspproj` no SigmaStudio 4.7.
4. Execute **Link Compile Download** e confirme primeiro a resposta plana de
   referência.
5. Não edite controles do compressor enquanto um dos scripts estiver rodando.

## Aplicar -6 dB somente em B1

1. Abra a janela de scripts do SigmaStudio (**Tools > Scripting** ou o comando
   equivalente da instalação).
2. Carregue `b1_apply_minus6db.sss` e execute o script.
3. Prossiga somente se aparecer a mensagem `PASS` confirmando os 136 bytes.
4. Repita no REW exatamente a medição usada para a referência.

Para evitar ambiguidade, nomeie as três curvas como `B1_0dB_before`,
`B1_minus6dB` e `B1_0dB_after`, preservando o mesmo nível de estímulo, ganho,
roteamento e janela do REW.

Resultado esperado, comparando com a referência:

- bem abaixo de 229,3 Hz: aproximadamente -6 dB;
- ao redor de 229,3 Hz: transição determinada pelo LR4, pelo somatório e pela
  compensação de fase;
- bem acima de 229,3 Hz: retorno gradual para aproximadamente 0 dB.

Isso não deve parecer um degrau ideal em 229,3 Hz. O ensaio reduz B1, uma banda
do banco, e mede sua recombinação com as demais bandas.

## Restaurar o estado linear

1. Carregue e execute `b1_restore_unity.sss`.
2. Prossiga somente se aparecer a mensagem `PASS`.
3. Repita a medição: ela deve coincidir com a referência dentro da repetibilidade
   do setup.

Um novo **Link Compile Download** também restaura a LUT linear gravada no projeto.

As chamadas usadas nos scripts seguem a interface oficial `ICRegisterWrite` /
`ICRegisterRead` do [manual de scripting do SigmaStudio](https://wiki.analog.com/_media/resources/tools-software/sigmastudio/developmentenvironment/sigmastudio_scripting.pdf),
seção 2.4, *Register Interface*.

## Calibracao do nivel do detector

Antes de gerar as LUTs CAMFIT, execute o ensaio descrito em
[`../rew/minus-six/B1_DETECTOR_CALIBRATION.md`](../rew/minus-six/B1_DETECTOR_CALIBRATION.md). Os
scripts `b1_detector_calibration.sss` e `b1_detector_restore_unity.sss`
identificam o nivel realmente visto pelo compressor a partir de medidas em dBV.

As LUTs com coeficientes diferentes sao transferidas em palavras de quatro
bytes. Uma transferencia unica de 136 bytes produziu divergencia exatamente
64 bytes apos o endereco inicial (`0x216C`); LUTs constantes haviam mascarado
esse limite porque a repeticao dos dados era indistinguivel.

Essa etapa e necessaria porque o datasheet fornece a faixa nominal do ADC, mas
a LUT deve incluir tambem a convencao RMS do algoritmo e a resposta do ramo do
banco de filtros.

## Teste da fatoracao LUT + bias

O export de 12/08/2026 inclui tres blocos `Gain (no slew)` entre `Add7` e
`Add8` na board `phasecomp`. O script `bias_factorization_apply_12db.sss`
valida essa arquitetura sem alterar o ganho teorico do sistema:

- escreve -12 dB nas 34 posicoes das LUTs B1 a B8;
- escreve +4 dB em cada um dos tres ganhos em cascata;
- preserva B9, que entra diretamente em `Add8`;
- transfere e verifica cada parametro em palavras de quatro bytes.

Os coeficientes 5.23 usados sao:

- -12 dB: `0x002026F3`;
- +4 dB: `0x00CADDC8`;
- unity: `0x00800000`.

A quantizacao produz ganho liquido calculado de apenas
`+0,00000031 dB`, efetivamente 0 dB.

Procedimento:

1. Execute **Link Compile Download**.
2. Salve no REW a referencia `bias_0dB_before`.
3. Execute `bias_factorization_apply_12db.sss` e prossiga somente com `PASS`.
4. Repita a mesma medicao como `bias_compensated`.
5. Execute `bias_factorization_restore_unity.sss`.
6. Repita a medicao como `bias_0dB_after`.

As tres curvas devem se sobrepor em magnitude e fase dentro da repetibilidade
do setup. A restauracao remove primeiro os ganhos positivos e somente depois
devolve as LUTs a unity, evitando ganho transitorio excessivo. Um novo
**Link Compile Download** tambem restaura o projeto salvo.

## Primeira prescricao CAMFIT: N1

O gerador reproduzivel
[`../../experiments/prescriptions/scripts/generate_sigma_adau1787_prescription.py`](../../experiments/prescriptions/scripts/generate_sigma_adau1787_prescription.py)
le a prescricao CAMFIT, descobre os enderecos diretamente no XML exportado e
gera os scripts em [`generated/N1`](generated/N1).

Para regenerar:

```bash
python3 experiments/prescriptions/scripts/generate_sigma_adau1787_prescription.py
```

O primeiro procedimento de bancada esta em
[`generated/N1/N1_INITIAL_VALIDATION.md`](generated/N1/N1_INITIAL_VALIDATION.md).
Ele usa os pontos eletricos B1/50 Hz que ja possuem calibracao de detector.
O ganho global CEC1 de -20 dB e os offsets B2 a B8 ainda nao fazem parte dessa
validacao inicial.

## Criterio de go/no-go

Para o teste B1, **GO** significa que a atenuacao aparece predominantemente na
primeira banda e a restauracao volta a referencia.

Para o teste de fatoracao, **GO** significa que os scripts informam `PASS` e as
tres curvas `bias_0dB_before`, `bias_compensated` e `bias_0dB_after` permanecem
sobrepostas em magnitude e fase dentro da repetibilidade do setup.

**NO-GO:** falha na leitura de volta, desvio persistente entre as curvas depois
da compensacao, resposta que nao retorna apos restauracao, ou ruido/instabilidade
inesperados. Nesse caso, faca novamente **Link Compile Download**, interrompa o
ensaio e preserve as capturas do REW e a mensagem apresentada pelo script.
