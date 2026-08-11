# EngineerZone update - ADAU1787 failures and supply sequencing

Target thread:
https://ez.analog.com/microcontrollers/precision-microcontrollers/f/q-a/604798/faulty-pcbs-with-adau1787

Planned attachments (stored under `evidence/`):

- `evidence/VBUS.png`
- `evidence/VBAT.png`
- `evidence/PMIC_power_paths.png`

## Comment to publish

Hi everyone,

I would like to provide an update after further investigation of the failed boards. The supply-sequencing behavior described below is currently a hypothesis under investigation, not yet a confirmed root cause.

### Failure localization

- Four of our five prototypes have failed during the debugging campaign.
- On the failed boards, we measure a low-resistance or short-circuit condition between the ADAU1787 IOVDD rail and GND.
- On one board, removing the nPM1100 did not clear the short.
- We then cut the IOVDD connection between the PMIC rail and the ADAU1787. The short remained on the ADAU1787 side, further indicating damage inside the codec's I/O supply domain rather than a persistent PMIC short.

### Relevant power architecture

- The nPM1100 VOUTB output directly generates the 1.8 V digital rail used by ADAU1787 IOVDD.
- The nPM1100 VSYS output supplies a separate XCL210C12 converter, which generates the 1.8 V analog rail used by ADAU1787 AVDD and HPVDD.
- REG_EN is connected to AVDD through the default-closed SB8 bridge; SB9 to GND is open. Therefore, the ADAU1787 internal regulator is enabled and generates its nominal 0.9 V DVDD supply.
- The external 0.9 V DVDD converter shown in the schematic is disconnected from the codec in the tested configuration because SB7 is open.
- The ADAU1787 PD pin is controlled by the nRF5340. PD has the ADAU1787 internal pull-down while it is not actively driven. PD was not included in the oscilloscope captures below, so its actual waveform still needs to be measured together with the supply rails.

I have attached a cropped schematic showing the VBUS/VBAT, VSYS, IOVDD and AVDD supply paths.

### Startup measurements

We captured startup under two input-power conditions. In both captures:

- yellow is the input supply, VBUS or VBAT;
- magenta is ADAU1787 AVDD/HPVDD;
- blue is ADAU1787 IOVDD.

With VBUS power, AVDD starts approximately 500 us before IOVDD.

With VBAT power, AVDD and IOVDD rise almost simultaneously. However, IOVDD reaches its steady-state voltage slightly before AVDD, producing a short interval during which IOVDD is higher than AVDD.

The ADAU1787 datasheet, Rev. A, states in the **Power Supply Sequencing** section on page 32:

> On power-up, AVDD and HPVDD must be powered up before or at the same time as IOVDD. Do not power up IOVDD when power is not applied to AVDD.

Could ADI please clarify the following points?

1. What AVDD voltage threshold is considered "power applied to AVDD" for this requirement?
2. Is there a maximum permitted time skew or voltage difference between AVDD/HPVDD and IOVDD during their ramps?
3. Is the brief condition observed with VBAT, where IOVDD reaches regulation slightly before AVDD, considered a sequencing violation?
4. Does holding PD low make an IOVDD-before-AVDD condition safe, or does the external rail-ordering requirement apply regardless of PD?
5. Could violating this sequencing requirement plausibly damage the IOVDD domain and result in a permanent IOVDD-to-GND short?
6. With PD low, are the digital input structures electrically isolated? What states are permitted on SDA, SCL, BCLK, FSYNC, SDATA and the multifunction GPIO pins while IOVDD or AVDD is absent or still ramping?
7. Is there a required rail order during power-down?

### Internal initialization sequence

Our current firmware initially holds PD low, releases it, waits 100 ms and then executes the SigmaStudio-generated download. The generated sequence begins by writing `CHIP_PWR = 0x17`, and the DSP memories are loaded before the firmware explicitly reads `POWER_UP_COMPLETE`.

Should the initialization instead strictly follow the staged sequence described on pages 29 to 31 of the datasheet?

1. Write `CHIP_PWR = 0x11` to set `POWER_EN = 1`.
2. Wait 35 ms for CM startup.
3. Write `CHIP_PWR = 0x15` to set `CM_STARTUP_OVER = 1`.
4. Configure and lock the PLL.
5. Wait for `PLL_LOCK = 1` and `POWER_UP_COMPLETE = 1`.
6. Initialize the DSP memories.
7. Write `CHIP_PWR = 0x17` to set `MASTER_BLOCK_EN = 1`.

Is the fixed 100 ms delay sufficient, or must `POWER_UP_COMPLETE` be polled before the DSP memories are accessed?

We can provide the complete Job File, additional waveforms, resistance measurements and failed devices if failure analysis is possible.

Thank you,

Joao Colombari
