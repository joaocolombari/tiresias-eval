# Tiresias - Risco de contenção entre GPIO e SPORT1 do ADAU1787

## Controle de revisão

| Item | Valor |
| --- | --- |
| Data da revisão | 01/08/2026 |
| Firmware | `felipepimentab/new-tiresias` |
| Commit de firmware | `ed4cc8d98bcc9de5055fbd59dd70a15bb78aec7d` |
| Definição de placa | `felipepimentab/tiresias-boards` |
| Commit de placa consultado | `58ef58e5486cfa0ad356f5b2a0795d182896cc44` |
| Relatório revisado | [`adau1787-startup.md`](./adau1787-startup.md) |
| Estado da hipótese | Aberta e tecnicamente plausível; ainda não confirmada por captura de registradores ou medição elétrica |

## Conclusão executiva

O relatório do Felipe descreve corretamente a maior parte da ordem de chamadas,
o download do SigmaStudio e a separação entre inicialização do codec e início do
stream. Entretanto, a revisão encontrou dois erros que afetam diretamente a
análise de risco:

1. O relatório afirma que MP3 a MP6 estão em P1.14, P1.15, P1.12 e P1.13. Na
   definição de placa publicada, esses sinais estão em P0.07, P0.06, P0.05 e
   P0.04, respectivamente. São exatamente os mesmos pinos selecionados pelo
   overlay para o SPORT1.
2. O relatório afirma que `STATUS2` é lido 10 ms depois do início do I2S. No
   commit revisado, a leitura ocorre dentro de `adau1787_init()`, imediatamente
   depois dos downloads Sigma e Fast e antes do início do stream. Não existe a
   espera de 10 ms descrita.

Consequentemente, o relatório não refuta o risco de contenção. Pelo contrário,
a definição de placa publicada confirma a sobreposição física entre os GPIOs
configurados pelo driver e os dutos do SPORT1.

Isso não prova que houve corrente destrutiva. Para confirmar contenção ainda é
necessário observar o estado efetivo dos registradores do nRF5340 e do
SDATAO1 do ADAU1787 durante a inicialização.

## Fontes usadas na revisão

- Firmware local: `FW/new-tiresias` no commit registrado acima.
- Overlay: `boards/tiresias_dk_nrf5340_cpuapp.overlay`.
- Driver: `src/drivers/adau1787.c`.
- I2S: `src/modules/audio_i2s.c` e `src/audio/audio_datapath.c`.
- Sequência Sigma/Fast: `src/SigmaStudioFiles/`.
- Definição externa de placa:
  [`tiresias_dk_nrf5340_cpuapp_common.dtsi`](https://github.com/felipepimentab/tiresias-boards/blob/58ef58e5486cfa0ad356f5b2a0795d182896cc44/eesc-usp/tiresias_dk/tiresias_dk_nrf5340_cpuapp_common.dtsi).
- Pinctrl externo de placa:
  [`tiresias_dk_nrf5340_cpuapp_common-pinctrl.dtsi`](https://github.com/felipepimentab/tiresias-boards/blob/58ef58e5486cfa0ad356f5b2a0795d182896cc44/eesc-usp/tiresias_dk/tiresias_dk_nrf5340_cpuapp_common-pinctrl.dtsi).

## Matriz de revisão do relatório do Felipe

| Afirmação do relatório | Revisão | Consequência |
| --- | --- | --- |
| O controlador publica `AUDIO_CMD_INIT` e a thread de áudio chama `audio_system_init()` | Confirmada | A ordem de alto nível está correta |
| `audio_datapath_init()` e `audio_i2s_init()` acontecem antes de `hw_codec_init()` | Confirmada | O pinctrl do I2S é aplicado antes da configuração GPIO do ADAU |
| O periférico I2S permanece ocioso até o início do stream | Confirmada | BCLK e LRCK regulares não devem existir durante o download Sigma |
| `!PD` é assertado, depois liberado, seguido de espera de 100 ms | Confirmada | Essa é a única espera explícita e efetiva antes do download |
| O delay Sigma `{0x00, 0x23}` resulta em 0 ms | Confirmada | O adaptador usa somente o primeiro byte em `k_msleep(*(pData))` |
| MP3 a MP6 estão em P1.14, P1.15, P1.12 e P1.13 | Refutada para o commit de placa publicado | A definição publicada usa P0.07, P0.06, P0.05 e P0.04 |
| O overlay realiza uma troca e move MP3 a MP6 para os pinos antigos do I2S | Refutada | O overlay altera apenas o pinctrl do I2S; não sobrescreve `mp3-gpios` a `mp6-gpios` |
| `STATUS2` é lido 10 ms após `nrfx_i2s_start()` | Refutada | A leitura ocorre durante `adau1787_init()`, antes do stream |
| Os locks reportados representam o estado após BCLK/LRCK iniciarem | Refutada no commit atual | `SPT1_LOCK=0` nessa leitura pode ser simplesmente consequência da ausência de clocks |
| O relatório descreve a sequência elétrica de AVDD e IOVDD | Incompleta | Ele descreve software e `!PD`, mas não a subida física das fontes |
| A dependência externa de placa está rastreada | Incompleta | O relatório cita o repositório irmão, mas não registra seu commit |

## Mapeamento efetivo do SPORT1

A definição de placa publicada fornece os GPIOs usados pelo driver:

| Propriedade do ADAU | Pino do nRF | Função física do ADAU |
| --- | --- | --- |
| `mp3-gpios` | P0.07 | MP3 / FSYNC1 |
| `mp4-gpios` | P0.06 | MP4 / BCLK1 |
| `mp5-gpios` | P0.05 | MP5 / SDATAO1 |
| `mp6-gpios` | P0.04 | MP6 / SDATAI1 |

O overlay do firmware seleciona exatamente os mesmos pinos para o I2S:

| Função do nRF I2S | Pino do nRF | Conexão no ADAU |
| --- | --- | --- |
| `I2S_LRCK_M` | P0.07 | FSYNC1 |
| `I2S_SCK_M` | P0.06 | BCLK1 |
| `I2S_SDIN` | P0.05 | SDATAO1 |
| `I2S_SDOUT` | P0.04 | SDATAI1 |

Não existe uma troca efetiva entre P0 e P1 no devicetree revisado. P1.14,
P1.15, P1.12 e P1.13 são os pinos do pinctrl base do I2S, associados ao caminho
original do SPORT0. O overlay muda o I2S para P0.06, P0.07, P0.04 e P0.05, mas
as propriedades `mp3-gpios` a `mp6-gpios` já apontam para esses mesmos pinos P0.

## Sequência real encontrada no commit

1. `audio_system_init()` chama `audio_datapath_init()`.
2. `audio_datapath_init()` chama `audio_i2s_init()`.
3. `audio_i2s_init()`:
   - configura HFCLKAUDIO em 12,288 MHz;
   - inicia HFCLKAUDIO;
   - aplica o pinctrl do I2S sobre P0.04 a P0.07;
   - inicializa a instância `nrfx_i2s` no estado ocioso.
4. `audio_system_init()` chama `hw_codec_init()` e `adau1787_init()`.
5. `adau1787_config_gpios()`:
   - configura `!PD` como saída ativa, mantendo o ADAU em power-down;
   - reconfigura P0.07, P0.06, P0.05 e P0.04 como
     `GPIO_OUTPUT_INACTIVE`.
6. `adau1787_power_up()` libera `!PD`.
7. O firmware espera 100 ms.
8. `default_download_IC_1_Sigma()` executa 208 escritas e uma solicitação de
   delay que atualmente resulta em 0 ms.
9. `default_download_IC_1_Fast()` executa duas escritas.
10. `adau1787_log_status_2()` lê `STATUS2` imediatamente.
11. A inicialização termina e o sistema aguarda um evento de streaming.
12. Somente depois, `audio_datapath_start()` chama `nrfx_i2s_start()`.

Portanto, entre os passos 5 e 12, os pinos compartilhados foram explicitamente
reconfigurados pela API GPIO depois de o pinctrl I2S ter sido aplicado.

## Risco elétrico no SPORT1

O duto crítico é P0.05:

```text
nRF P0.05 / I2S_SDIN  <--- 33 ohms --->  ADAU MP5 / SDATAO1
```

No funcionamento normal, P0.05 deve ser entrada no nRF e SDATAO1 deve ser saída
no ADAU. Porém, `adau1787_config_gpios()` solicita que P0.05 seja uma saída GPIO
baixa.

O download Sigma usa `SAI_CLK_PWR = 0x0C`:

```text
SPT0_IN_EN  = 0
SPT0_OUT_EN = 0
SPT1_IN_EN  = 1
SPT1_OUT_EN = 1
```

Assim, o download habilita o caminho de saída do SPORT1 enquanto o estado
efetivo de P0.05 no nRF ainda precisa ser confirmado.

Se o nRF mantiver P0.05 como saída baixa e o ADAU dirigir SDATAO1 alto, haverá
contenção. Desprezando as resistências internas das duas saídas, o limite
idealizado seria:

```text
I = 1,8 V / 33 ohms = aproximadamente 55 mA
```

Essa não é uma corrente medida. É um pior caso teórico usado para justificar a
investigação. O limite absoluto indicado para corrente em pinos que não são de
alimentação do ADAU1787 é de aproximadamente `+/-20 mA`.

Uma contenção sustentada ou repetitiva pode:

- injetar corrente no domínio IOVDD;
- aquecer o driver de SDATAO1;
- causar degradação ou comportamento intermitente;
- contribuir para uma falha interna posterior entre IOVDD e GND.

FSYNC1, BCLK1 e SDATAI1 são menos críticos quanto à contenção se o ADAU estiver
em modo escravo e esses três sinais permanecerem entradas. Suas direções ainda
devem ser confirmadas durante todo o download.

## Comparação com o SPORT0

O risco não aparece da mesma maneira no SPORT0:

| Aspecto | SPORT0 | SPORT1 |
| --- | --- | --- |
| Selecionado pelo overlay ativo | Não | Sim, P0.04 a P0.07 |
| Forçado como GPIO pelo driver | Não há `codec_mp0` a `codec_mp2` | MP3 a MP6 viram saídas baixas |
| Entrada habilitada no ADAU | Não | Sim |
| Saída habilitada no ADAU | Não | Sim |
| Risco de contenção atual | Baixo | Possível em P0.05 / SDATAO1 |

O download escreve os controles elétricos dos pads do SPORT0:

```text
FSYNC0_CTRL  = 0x05
BCLK0_CTRL   = 0x05
SDATAO0_CTRL = 0x04
SDATAI0_CTRL = 0x05
```

Esses valores configuram drive e slew, mas não habilitam o fluxo funcional. Os
campos decisivos continuam sendo `SPT0_IN_EN=0` e `SPT0_OUT_EN=0`.

Consequentemente, `SPT0_LOCK=0` é esperado enquanto o SPORT0 estiver desligado
e não constitui, isoladamente, evidência de falha de hardware.

## Correção sobre a leitura de STATUS2

O relatório do Felipe coloca a leitura de `STATUS2` depois de o stream começar,
mas o código atual faz a leitura em `adau1787_init()`, antes de
`nrfx_i2s_start()`.

Isso altera a interpretação dos logs:

- `SPT1_LOCK=0` pode ser normal porque BCLK e LRCK ainda não começaram;
- o log atual não comprova se o SPORT1 trava corretamente durante o stream;
- não existe hoje a captura pós-start descrita no relatório;
- a leitura é apenas diagnóstica e não bloqueia a inicialização.

Uma revisão futura pode manter duas leituras claramente identificadas:

1. `STATUS2_PRE_I2S`, depois do download e antes do stream;
2. `STATUS2_POST_I2S`, depois do início dos clocks e de um intervalo definido.

## Limite do relatório quanto a AVDD e IOVDD

O relatório descreve a sequência lógica do firmware, não a sequência elétrica
das fontes. O firmware controla `!PD`, mas não controla diretamente os enables
de AVDD ou IOVDD.

Portanto, não é possível concluir a partir do relatório:

- qual fonte cruza primeiro seus limiares na energização;
- se IOVDD permanece presente sem AVDD na subida ou na descida;
- se há overshoot em IOVDD;
- se algum sinal digital fica ativo enquanto IOVDD ou AVDD está ausente.

Esses pontos exigem captura simultânea de VSYS, AVDD, IOVDD e `!PD` na placa.

## Evidências ainda necessárias do Felipe

### Estado do nRF5340

Registrar nos seguintes marcos: depois de `audio_i2s_init()`, depois de
`adau1787_config_gpios()`, depois do download Sigma e depois de
`nrfx_i2s_start()`:

- `GPIO0.PIN_CNF[4..7].DIR`;
- `GPIO0.PIN_CNF[4..7].INPUT`;
- bits 4 a 7 de `GPIO0.OUT`;
- `I2S0.PSEL.SDIN`;
- `I2S0.PSEL.SDOUT`;
- `I2S0.PSEL.SCK`;
- `I2S0.PSEL.LRCK`;
- `I2S0.ENABLE`.

Pergunta decisiva:

> P0.05 continua eletricamente como saída baixa durante algum intervalo em que
> MP5/SDATAO1 está habilitado como saída no ADAU?

### Estado do ADAU1787

Confirmar por leitura de registradores ou pela exportação Sigma:

- função selecionada para MP5;
- instante em que `SPT1_OUT_EN` passa para 1;
- estado ou alta impedância de SDATAO1 antes de BCLK/FSYNC;
- SPORT1 em modo mestre ou escravo;
- `POWER_EN` e `POWER_UP_COMPLETE`;
- `STATUS2` antes e depois do início do I2S.

### Rastreabilidade da build

Arquivar junto ao ensaio:

- hash do firmware;
- hash do repositório `tiresias-boards`;
- `.config` efetivo;
- `zephyr.dts` efetivo;
- overlay utilizado;
- log completo de boot e início de stream.

Sem o hash da dependência externa de placa, a build não é completamente
reproduzível e o mapeamento de pinos pode ficar ambíguo.

## Critério de fechamento da hipótese

### Confirmada

Em algum intervalo após a liberação de `!PD` ou durante/depois do download, o
nRF mantém P0.05 como saída enquanto MP5/SDATAO1 está habilitado como saída no
ADAU.

### Refutada

É demonstrado por registradores que P0.05 permanece como entrada ou desconectado
durante todo o intervalo em que SDATAO1 pode dirigir a linha.

### Inconclusiva

A ordem das chamadas é conhecida, mas não há captura dos registradores de
direção/PSEL ou do estado elétrico da linha.

## Direção de correção, caso o risco seja confirmado

Não aplicar alterações na placa funcional antes de fechar a análise. As opções
pequenas e reversíveis a avaliar são:

1. Não tratar MP3 a MP6 como GPIOs genéricos do nRF quando esses mesmos pinos
   pertencem ao I2S.
2. Manter P0.05 como entrada ou desconectado desde o boot.
3. Definir estado seguro para P0.04 a P0.07 antes de liberar `!PD`.
4. Reaplicar o pinctrl I2S depois da configuração do codec, se isso for
   necessário para restaurar `PIN_CNF`.
5. Manter SDATAO1 em alta impedância até o nRF estar preparado para receber.
6. Adicionar logs ou asserts temporários de `PIN_CNF`, `PSEL` e `ENABLE`.
7. Mover ou duplicar a leitura de `STATUS2` para observar o estado depois do
   início real do I2S.
8. Corrigir a decodificação do delay Sigma para que `{0x00, 0x23}` não resulte
   silenciosamente em 0 ms, após confirmar a unidade e o endianness esperados.

Nenhum patch de firmware ou retrabalho de hardware é proposto como concluído
neste documento. A próxima decisão depende das capturas solicitadas.
