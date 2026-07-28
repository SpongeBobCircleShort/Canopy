# Closed-Set Acoustic Classifier — Independent Vetting (2026-07-07)

Scope: the closed-set CNN threat classifier lineage in `models/audio/`
(`threat_cnn_*`), i.e. the model that classifies a clip into
`{chainsaw, gunshot, vehicle, fire_crackle, background_unknown}`. Distinct from
the open-set anomaly detector. All numbers below were **re-run from the
artifacts**, not copied from stored metrics (stored metrics reproduced exactly).

## Verdict

**Not deployable as a threat classifier.** Usable only as a frozen embedding
backbone — which is how it is now used — and even there it is chance-level
cross-site (see the open-set evaluation, `MODEL_STATUS.md` 2026-07-07). The
pivot to open-set was the correct call; this report is the quantitative
justification.

Two independent failure modes:

1. **In-domain (public data), it fails its own false-positive targets.**
2. **Cross-site (the deployment condition), detection collapses** once background
   false positives are controlled.

## What the models are

All share: CNN, 16 kHz, 4 s clips, 64-mel, 5 classes. Trained on mixes of public
audio (Kaggle vehicle/chainsaw/gunshot/fire, ESC-50, FSD50K, FSC22, DCASE) plus
RFCx rainforest clips (chainsaw + background) in the `forest_*` lineage. The
model served as the production **embedder** is `threat_cnn_kaggle_augmented_v1`
(per `docs/anomaly-detection.md`); no classifier is wired to serve alerts by
default (`audio_model_path` defaults to `None`).

## Leakage audit — PASS

Source-clip stems (filename with RFCx `_<start>-<end>` window suffix stripped, so
clips from the same source recording collapse to one key) across train/val/test:

| Manifest | train∩test | val∩test | train∩val |
| --- | --- | --- | --- |
| `kaggle_augmented_v1` | 0 | 0 | 0 |
| `forest_v1b` | 0 | 0 | 0 |
| `forest_v1b_tambopata_holdout` | 0 | 0 | 0 |

No clip- or recording-level leakage. Calibration thresholds are selected on
`val` (via `calibrate_thresholds.py`), not on `test` — methodologically sound.

## Finding 1 — headline accuracy is imbalance-inflated

`threat_cnn_kaggle_augmented_v1` on its own `test` split (in-domain public data):

- Raw argmax: **accuracy 0.907** but **macro-F1 0.540**. The gap is class
  imbalance — the test split is vehicle-dominated (training manifest is ~83%
  `kaggle_vehicle_type`). Accuracy is not a meaningful summary here; macro-F1 is.
- Raw-argmax **background threat-false-positive rate = 0.556** (60 of 108
  background clips are called a threat). At raw argmax the model "works" only by
  alarming on half of all background.

## Finding 2 — even in-domain, it misses its own FP targets

Applying the model's stored deployment thresholds (val-calibrated) to the
in-domain test split:

| | chainsaw | gunshot | vehicle | fire | background |
| --- | --- | --- | --- | --- | --- |
| calibrated recall | 0.404 | 0.610 | 0.747 | 0.413 | 0.806 |
| per-class bg-FP | 0.019 | 0.074 | 0.083 | 0.019 | — |
| config max bg-FP target | 0.03 | 0.02 | 0.04 | 0.03 | — |

Overall background threat-FP = **0.194** (≈1 in 5 background clips alarms).
gunshot (3.7×) and vehicle (2×) blow through their own configured FP ceilings.
Thresholding to control FP roughly halves threat recall (macro-F1 0.540 → 0.317).

## Finding 3 — cross-site, detection collapses (the deployment reality)

`threat_cnn_forest_v1b_tambopata_holdout` (all tambopata clips held out; 41
chainsaw + 72 background in test), re-run:

| Operating point | chainsaw recall | background threat-FP |
| --- | --- | --- |
| Raw argmax | 0.976 | 0.500 |
| Val-calibrated (deployment) | **0.195** | 0.000 |

Other threat classes at the calibrated point: gunshot/vehicle/fire recall =
**0.0**. Interpretation: on an unseen site, controlling background false
positives suppresses essentially all detection. The raw model finds chainsaws
only by also flagging half of held-out background. This is not a threshold-tuning
problem — it is the absence of a decision boundary that transfers across sites.

Note the contrast with `forest_v1b` (random split, **same sites in train and
test**): calibrated chainsaw recall 0.239 at bg threat-FP 0.208. Same-site test
looks only marginally better and still fails the FP budget — the random-split
"forest" numbers are optimistic and should not be read as deployment estimates.

## What is solid (fair credit)

- No split leakage; recording-aware.
- Thresholds calibrated on validation, not test.
- Stored metrics reproduce exactly on re-run (artifacts are trustworthy).
- The failure is already honestly documented internally (`MODEL_STATUS.md`), and
  the response (open-set + frozen general-purpose embedding) is the right one.

---

# Addendum (2026-07-08): hypothesis-driven experiments

Reframed from "the model fails" to testable hypotheses, addressing review
feedback. New tooling (all numpy-metric cores unit-tested, CI-safe):
`crossdomain_metrics.py`, `eval_crossdomain.py`, `aggregate_crossdomain.py`,
`represent_probe.py`. Reports in `research/audio/reports/crossdomain/`.

**Central thesis.** Random splits overestimate deployment performance for
bioacoustic threat detection; closed-set softmax classifiers fail under
site-level shift — partly because their representation encodes recording site as
strongly as event class — while false-positive control at a fixed budget, not
accuracy or ranking, is the binding constraint.

## Design (no contamination)

The public-trained ladder (`kaggle_*`, `expanded_*`) contains **0 RFCx clips**
(verified), so evaluating it on held-out RFCx sites is an uncontaminated
public→forest transfer test — pure inference, no retraining. `forest_v1/v1b`
trained on every site and are excluded from cross-site claims;
`forest_v1b_tambopata_holdout` is the one clean forest-trained point. Four sites
carry enough chainsaw+background for evaluation: warsi (412/198), tambopata
(41/72), romania (30/15), pooks (10/12). All metrics carry clip-level bootstrap
95% CIs (1000×).

## H4/H5 — the binding constraint is calibration, not ranking (STRONGEST)

`threat_cnn_kaggle_augmented_v1`, deployment-calibrated (its own val thresholds),
per held-out site:

| Site | chainsaw recall [95% CI] | background threat-FP [CI] | chainsaw-vs-bg AUC [CI] |
| --- | --- | --- | --- |
| tambopata | 0.000 [0.000,0.000] | 0.014 [0.000,0.045] | 0.559 [0.450,0.670] |
| warsi | 0.002 [0.000,0.007] | 0.066 [0.033,0.102] | 0.652 [0.605,0.695] |
| romania | 0.000 [0.000,0.000] | 0.000 [0.000,0.000] | **0.964** [0.906,1.000] |
| pooks | 0.000 [0.000,0.000] | 0.167 [0.000,0.385] | 0.725 [0.471,0.917] |

Recall is ~0 at **every** site, so the collapse is not tambopata-specific (H3
addressed). The romania row is the crux: the score ranks chainsaws almost
perfectly (**AUC 0.964**) yet the source-calibrated threshold detects **nothing**
(recall 0.000). The classifier can discriminate; the decision threshold simply
does not transfer across domains. This is a calibration/operating-point failure,
not a discrimination failure — accuracy and AUC hide it; recall-at-fixed-FP
exposes it.

## H1/H10 — training-recipe ablation on a common held-out site (warsi)

Deployment-calibrated, each recipe under its own val thresholds:

| Training recipe | chainsaw recall | background threat-FP | AUC |
| --- | ---: | ---: | ---: |
| baseline (balanced public) | 0.005 | 0.030 | 0.580 |
| + augmentation | 0.002 | 0.066 | 0.652 |
| + hard negatives | **0.495** | 0.136 | **0.720** |
| + more hard negatives | 0.012 | 0.197 | 0.682 |
| + expanded set | 0.000 | 0.854 | 0.654 |
| + DCASE machine negs | 0.022 | 0.556 | 0.632 |
| + conservative bg | 0.000 | 0.040 | 0.661 |

Hard-negative mining is the **only** intervention that meaningfully recovers
cross-site recall (0.495) and gives the best separability (AUC 0.720) — but at
13.6% background-FP, above the 10% budget, on the highest-support site. No public
recipe is simultaneously sensitive and FP-compliant cross-site. (Recipes are not
strictly nested supersets; read as a recipe comparison across the deployed
lineage, not a perfectly controlled ablation.)

## H2 — the representation encodes site, not just event

Linear probes (5-fold stratified CV, balanced accuracy) on the same frozen
embeddings of 429 forest clips across 7 sites — models that saw **no** forest
audio in training:

| Embedding | predict class (chainsaw/bg), chance 0.50 | predict site (7-way), chance 0.14 |
| --- | ---: | ---: |
| supervised CNN | 0.854 | **0.600** |
| frozen AudioSet CNN14 | 0.839 | 0.508 |

Recording site is linearly decodable at 0.60 (≈4× chance) from the supervised
CNN embedding, and more so than from the general-purpose PANNs embedding (0.508),
while class-discrimination is essentially tied (0.85 vs 0.84). A model that never
trained on forest still geometrically organizes forest clips by site — a concrete
mechanism for the transfer failure, and evidence that the supervised CNN absorbs
site-correlated acoustic characteristics more than a general encoder does. PCA
visualizations (by class vs by site) for both embeddings:
`research/paper/aaai27-listening-without-labels/figures/pca_*.pdf`.

## Wording correction (review item 7)

The original "no transferable decision boundary" overreaches. Evidence-faithful
statement: *the learned decision boundary exhibits poor cross-site generalization
under our evaluation, and the source-calibrated operating point does not transfer
even where class scores remain separable.*

## Still open (honest gaps, next phases)

- ROC/PR curves + score-distribution/reliability plots (H4/H5 visuals) — score
  arrays are being cached for this.
- Foundation baselines beyond PANNs (AST via `transformers`, CLAP via pip; BEATs
  not locally available).
- Failure taxonomy (which background subtypes trigger FPs) and dataset
  characterization from RFCx metadata (device/weather/annotation-agreement are
  **not** in the release and will be flagged, not invented).
- Training-seed variance (a few configs ×3 seeds); current CIs are eval-only
  bootstrap.

## Reproduce

```bash
# In-domain (public) test — production embedder
python -m research.audio.evaluate \
  --model models/audio/threat_cnn_kaggle_augmented_v1 \
  --manifest data/audio/manifests/threat_manifest_kaggle_augmented_v1.csv --split test

# Cross-site held-out test
python -m research.audio.evaluate \
  --model models/audio/threat_cnn_forest_v1b_tambopata_holdout \
  --manifest data/audio/manifests/threat_manifest_forest_v1b_tambopata_holdout.csv --split test

# Addendum experiments
python -m research.audio.eval_crossdomain --model models/audio/<model> \
  --manifest data/audio/manifests/threat_manifest_forest_v1b_<site>_holdout.csv --split test
python -m research.audio.aggregate_crossdomain --ablation-site warsi
python -m research.audio.represent_probe --panns --min-site-count 20 --plot
```

Raw metrics land in `<model>/test_metrics.json`; the val-calibrated operating
point is `<model>/test_metrics_deployment_thresholds.json`. Leakage audit script:
inline in this session (stem-key intersection over splits).
```
