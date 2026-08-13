# Curvas automáticas N1

Salve aqui a sessão REW `.mdat` com as seis curvas unity/N1 descritas em
`../N1_REW_CURVE_PROTOCOL.md`, além das respostas e razões exportadas em texto.

## Validação de 1M

As seis curvas de 45, 65 e 85 dB SPL equivalentes foram adquiridas em 13 de
agosto de 2026 e processadas por
`experiments/prescriptions/scripts/analyze_n1_rew_curves.py`.

Os resultados estão em `results/`:

- `N1_1M_VALIDATION.md`: conclusão e métricas;
- `N1_1M_centre_validation.csv`: resultados nos centros de banda;
- `N1_1M_gain_validation.svg` e `.png`: curvas medidas, modelo e tons
  estacionários.
- `N1_1M_2M_CONVERGENCE.md`: decisão sobre a influência da duração do sweep;
- `N1_1M_2M_convergence_centres.csv`: comparação por centro de banda;
- `N1_1M_2M_convergence.svg` e `.png`: diferença 2M − 1M em frequência.

A aquisição de 45 dB SPL está contaminada por ruído de rede e serve apenas
para validação qualitativa. A verificação 1M/2M confirmou convergência em
85 dB SPL e estabilidade prática em 65 dB SPL, com desvio marginal de 0,232 dB
apenas em B6. Em 45 dB SPL, a convergência permanece inconclusiva devido à
contaminação.
