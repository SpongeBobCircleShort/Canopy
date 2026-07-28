# Cross-site vetting — aggregated tables

Public-trained models (0 RFCx clips) evaluated on held-out RFCx sites; pure inference, no contamination. Deployment thresholds are each model's own validation-calibrated thresholds.

### Multi-site generalization: threat_cnn_kaggle_augmented_v1 (deployment-calibrated, 95% CI)

| Held-out site | n_chain | n_bg | Chainsaw recall [CI] | Background threat-FP [CI] | AUC [CI] |
| --- | ---: | ---: | --- | --- | --- |
| tambopata | 41 | 72 | 0.000 [0.000,0.000] | 0.014 [0.000,0.045] | 0.559 [0.450,0.670] |
| warsi | 412 | 198 | 0.002 [0.000,0.007] | 0.066 [0.033,0.102] | 0.652 [0.605,0.695] |
| romania | 30 | 15 | 0.000 [0.000,0.000] | 0.000 [0.000,0.000] | 0.964 [0.906,1.000] |
| pooks | 10 | 12 | 0.000 [0.000,0.000] | 0.167 [0.000,0.385] | 0.725 [0.471,0.917] |

### Ablation ladder on held-out site: warsi (deployment-calibrated)

| Training recipe | Chainsaw recall | Background threat-FP | chainsaw-vs-bg AUC |
| --- | ---: | ---: | ---: |
| baseline (balanced public) | 0.005 | 0.030 | 0.580 |
| + augmentation | 0.002 | 0.066 | 0.652 |
| + hard negatives | 0.495 | 0.136 | 0.720 |
| + more hard negatives | 0.012 | 0.197 | 0.682 |
| + expanded set | 0.000 | 0.854 | 0.654 |
| + DCASE machine negs | 0.022 | 0.556 | 0.632 |
| + conservative bg | 0.000 | 0.040 | 0.661 |
