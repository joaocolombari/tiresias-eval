# Teste de alimentação pela interface de debug

## Objetivo

Verificar se a conexão de um nRF5340 DK energizado à interface SWD de uma placa
Tiresias sem alimentação intencional, com a ponte `SB19` fechada, produz tensão
e atividade nos sinais digitais conectados ao ADAU1787.

## Hipótese

Com a ponte `SB19` fechada, o nRF5340 DK fornece `VIO_REF` ao dispositivo
externo conectado à interface de debug. Essa alimentação poderia energizar
parcialmente o nRF5340 da placa Tiresias e fazê-lo executar o firmware já
gravado. Nesse estado, o microcontrolador poderia dirigir os sinais das
interfaces I²C e I²S enquanto o ADAU1787 permanecesse sem alimentação
intencional.

O datasheet do ADAU1787 especifica, para os pinos digitais, uma faixa absoluta
de tensão entre `-0,3 V` e `IOVDD + 0,3 V`. Portanto, caso `IOVDD` permanecesse
em `0 V`, tensões superiores a `0,3 V` nesses pinos excederiam essa
especificação e poderiam injetar corrente no domínio de alimentação do codec.

## Procedimento experimental

### Preparação

1. Uma fonte de bancada, ajustada para `1,8 V`, foi conectada diretamente ao
   pino `VDD` de uma placa Tiresias cujo PMIC havia sido removido previamente.
2. Com a placa alimentada pela fonte, um J-Link EDU Mini foi usado para gravar
   o firmware no nRF5340.
3. O firmware utilizado habilita as interfaces I²C e I²S e gera atividade nos
   respectivos sinais.

### Teste

Após a gravação, a fonte de bancada foi desconectada da placa Tiresias. Em
seguida, a placa foi conectada, pela interface SWD, a um nRF5340 DK energizado e
com a ponte `SB19` fechada.

Nessa configuração, foram feitas medições com multímetro e osciloscópio nos
seguintes pontos de teste:

| Ponto de teste | Sinal | Descrição |
| --- | --- | --- |
| TP17 | FSYNC1/MP3 | Sincronismo de quadro da interface I²S |
| TP18 | BCLK1/MP4 | Clock de bits da interface I²S |
| TP19 | SDATAI1/MP6 | Entrada de dados seriais de áudio |
| TP20 | SDATAO1/MP5 | Saída de dados seriais de áudio |
| TP27 | SCL | Clock da interface I²C |
| TP28 | SDA | Dados da interface I²C |

## Resultados

### Interface I²S

![Atividade observada nos sinais da interface I²S](./images/NewFile4.png)

![Transiente observado nos sinais da interface I²S](./images/NewFile5.png)

Legenda dos canais:

- amarelo: `VDD`;
- azul escuro: `SDATAI1`;
- magenta: `BCLK1`;
- ciano: `FSYNC1`.

As capturas mostram atividade nos sinais da interface I²S mesmo após a remoção
da fonte de bancada. Os valores máximos indicados pelo osciloscópio ficam em
torno de `0,64 V` a `0,66 V`.

### Interface I²C

![Tensão observada nos sinais da interface I²C](./images/NewFile7.png)

Legenda dos canais:

- amarelo: `VDD`;
- ciano: `SDA`;
- magenta: `SCL`.

Também foram observadas tensões nos sinais `SDA` e `SCL`, com máximos em torno
de `0,64 V` a `0,66 V`, apesar de a placa Tiresias não estar conectada à fonte
de bancada.

## Conclusão

A conexão ao nRF5340 DK com `SB19` fechada produziu uma tensão residual em
`VDD` e atividade nas interfaces I²C e I²S da placa Tiresias. O resultado é
compatível com a hipótese de que a interface de debug alimenta parcialmente o
alvo e permite a execução do firmware previamente gravado.

Se `IOVDD` estivesse em `0 V`, os máximos observados, entre aproximadamente
`0,64 V` e `0,66 V`, excederiam em `0,34 V` a `0,36 V` o limite absoluto de
`IOVDD + 0,3 V` especificado para os pinos digitais do ADAU1787. Entretanto,
`IOVDD` e a corrente injetada nos pinos do codec não foram registradas nas
capturas apresentadas. Assim, o experimento demonstra a presença de tensão e
atividade indesejadas, mas não comprova, isoladamente, que essa condição tenha
causado dano ao ADAU1787.

## Referências

- [nRF5340 DK — configuração das pontes de solda](https://docs.nordicsemi.com/r/bundle/ug_nrf5340_dk/page/ug/dk/solder_bridge.html)
- [ADAU1787 — datasheet, Rev. A](https://www.analog.com/media/en/technical-documentation/data-sheets/adau1787.pdf)
