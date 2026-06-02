# Canopy Field Audio Data Requirements

This document is the collection specification for conservation partners who want Canopy acoustic alerts to work in their own forests. The current acoustic classifier is a research prototype. It should not be treated as a reliable field detector until it passes a held-out field validation using data collected from the same kind of sites, microphones, and operating conditions as the deployment.

## Collection Target

Canopy needs paired field data from each deployment area:

- Forest-at-rest background recordings from the actual monitoring sites.
- Verified examples of the threats the partner wants Canopy to detect.
- Metadata that ties each recording to a site, device, time, and human annotation.

Do not collect more public internet audio for this purpose. The known blocker is domain mismatch: public and urban datasets do not sound like the target deployment environment.

## Recording Sites

A recording site is one fixed acoustic monitoring location: one microphone or device position with a stable GPS coordinate, habitat type, and nearby soundscape. Treat two locations as different sites if they are more than 1 km apart, use different device models, sit in meaningfully different habitat, or have different human noise exposure such as road, river, village, trail, or logging edge.

Minimum viable collection:

- 3 recording sites from the same conservation project.
- Each site must have background recordings.
- At least 3 sites must contain verified chainsaw examples before chainsaw confidence can be considered for fusion scoring.
- For chainsaw and vehicle, no single site may provide more than 40% of verified examples for that class.
- For gunshot minimum-viable collection, no single site may provide more than 60% of verified examples because safe verified gunshot data may be harder to collect.

Recommended collection:

- 8 to 12 recording sites across the project area.
- Include at least 2 quiet interior forest sites, 2 edge or trail sites, 2 road or river-adjacent sites if relevant, and 2 sites where human activity is expected.
- Keep the same recording device type at all sites when possible. If multiple device types are used, collect background and threat examples on each type.

Why this matters:

- The latest `forest_v1b` model looked strong on familiar audio but failed a site-held-out validation. It learned site-specific sound patterns instead of a reliable threat boundary.
- Holding out complete sites during evaluation is the only way to estimate whether the classifier will work at a new sensor location.
- A 3-site minimum gives Canopy one site for held-out validation while still leaving multiple sites for training. The recommended 8 to 12 sites reduces the chance that the model becomes a detector for one microphone, one habitat, or one local background pattern.

## Background Recordings

Minimum viable background per site:

- 24 total hours per site.
- Spread the 24 hours across at least 2 calendar days.
- Include at least 3 hours in each time block:
  - Dawn: 04:00-07:00 local time.
  - Day: 10:00-15:00 local time.
  - Dusk: 17:00-20:00 local time.
  - Night: 22:00-03:00 local time.

Recommended background per site:

- 72 total hours per site.
- Spread across at least 7 calendar days.
- Include at least one dry period and one wet or windy period if those conditions occur naturally during the collection window.

Background content rules:

- Label background as `background_unknown`.
- Background clips must not contain audible chainsaw, gunshot, illegal vehicle, aircraft, or field-team speech near the microphone.
- Natural sounds such as insects, birds, rain, wind, streams, branches, and distant non-threat human activity should remain in the data.
- Do not apply noise reduction, voice isolation, automatic gain filters, or music/audio cleanup tools.

Preferred recording format:

- Continuous files of 5 to 30 minutes each, or scheduled recordings such as 1 minute every 5 minutes.
- Canopy can slice long files into training clips after ingestion.
- If manual clips are easier, provide 10 to 60 second clips.

## Verified Threat Examples

Each threat example must be a real, verified event. Do not use imitations, synthetic audio, movie audio, or unlabeled internet clips. Do not stage unsafe or illegal activity. Controlled examples are acceptable only when the partner can conduct them legally and safely.

### Chainsaw

Minimum viable:

- 90 verified chainsaw events total.
- At least 30 events from each of 3 recording sites.
- Each event should include 10 to 60 seconds of audio.
- Include at least 5 seconds before the chainsaw starts and 5 seconds after it stops when available.

Recommended:

- 240 verified chainsaw events total.
- At least 20 events from each of 8 to 12 sites.
- Include distance variation: near under 100 m, mid 100 to 500 m, and far over 500 m when known.
- Include operation variation: idle, revving, active cutting, intermittent cutting, and multiple saws when they occur.

Label:

- Use `chainsaw`.
- Add subtype notes such as `idle`, `cutting`, `revving`, `distant`, `multiple_saws`, or `unknown_mode`.

### Vehicle

Minimum viable:

- 90 verified vehicle events total.
- At least 30 events from each of 3 recording sites.
- Each event should include 10 to 60 seconds of audio.

Recommended:

- 240 verified vehicle events total.
- At least 20 events from each of 8 to 12 sites.
- Include the locally relevant vehicle types: motorcycle, truck, ATV, tractor, boat, or aircraft.
- Include approach, pass-by, idle, and departure when available.

Label:

- Use `vehicle`.
- Add subtype notes such as `motorcycle`, `truck`, `boat`, `atv`, `tractor`, `aircraft`, or `unknown_vehicle`.

### Gunshot

Minimum viable:

- 30 verified gunshot events total.
- Events should come from at least 2 recording sites.
- Each event should include 10 to 60 seconds of audio.
- Multiple shots in one continuous incident should share one `event_id`; mark the number of shots in metadata.

Recommended:

- 120 verified gunshot events total.
- Events should come from at least 6 recording sites.
- Include near, mid, and distant shots when known.
- Include different firearm types only if verified by the partner; otherwise use `unknown_firearm`.

Label:

- Use `gunshot`.
- Add subtype notes such as `single_shot`, `multiple_shots`, `distant`, `near`, `unknown_firearm`, or `verified_patrol_report`.

Safety rule:

- Do not create gunshot recordings unless the activity is lawful, planned, and approved by the partner organization. Opportunistic verified incidents, ranger patrol confirmations, or legal range recordings from matching field equipment are acceptable.

## Clip Format and Naming

Preferred audio format:

- WAV or FLAC.
- 16-bit PCM or better.
- Mono or stereo accepted.
- Minimum sample rate: 16 kHz.
- Recommended sample rate: 44.1 kHz or 48 kHz.
- Avoid MP3, AAC, WhatsApp voice notes, or files processed by noise suppression.

Clip duration:

- Background clips: 10 to 60 seconds if manually clipped, or long files up to 30 minutes if continuous.
- Threat event clips: 10 to 60 seconds.
- If an event lasts longer than 60 seconds, keep the full raw file and add event start/end timestamps in the metadata.

Required filename pattern for manual clips:

```text
<site_id>__<device_id>__<YYYYMMDD>T<HHMMSS>Z__<label>__<event_id>.wav
```

Examples:

```text
peru-tambo-01__audiomoth-017__20260602T104533Z__chainsaw__evt-00042.wav
peru-tambo-01__audiomoth-017__20260602T231500Z__background_unknown__bg-00318.wav
peru-road-03__guardian-002__20260603T071208Z__vehicle__evt-00104.wav
```

Allowed labels:

- `background_unknown`
- `chainsaw`
- `vehicle`
- `gunshot`

Use one label per clip. If a clip contains both background and a threat, label it as the threat. If a clip contains two threat types, split it into separate clips if possible; otherwise use the dominant threat and note the secondary sound in metadata.

## Equipment Requirements

Acceptable equipment:

- Dedicated acoustic sensors such as AudioMoth, Wildlife Acoustics, RFCx Guardian, Arbimon-compatible recorders, or equivalent fixed-location recorders.
- Handheld recorders such as Zoom, Tascam, Sony, or equivalent devices.
- Consumer phones are acceptable for early pilot data only if they record at 16 kHz or higher and the device model is recorded in metadata.

Minimum device settings:

- Sample rate: 16 kHz or higher.
- Bit depth: 16-bit or higher.
- Channels: mono or stereo.
- Automatic gain control: off if the device allows it.
- Noise reduction: off.
- File format: WAV or FLAC when possible.

Deployment setup:

- Mount fixed sensors 1.5 to 3 m above ground when practical.
- Use the same mounting height and microphone orientation across sites when possible.
- Use weather protection or a windscreen when available.
- Record a 10 second spoken setup note only before the formal collection starts, not during background collection.
- Do not hold or move the device during background recordings.

Consumer-phone constraint:

- Phone recordings can help with early labeling examples, but a model intended for fixed forest sensors must be trained and validated on those fixed sensors before deployment.

## Required Metadata

Provide one CSV file per delivery named `canopy_audio_metadata.csv`. Each row should describe one audio file or one labeled event inside a longer audio file.

Required columns:

| Column | Example | Requirement |
| --- | --- | --- |
| `organization_id` | `partner-org-01` | Partner or project identifier. |
| `site_id` | `peru-tambo-01` | Stable site ID used in filenames. |
| `device_id` | `audiomoth-017` | Stable recorder ID or phone ID. |
| `file_name` | `peru-tambo-01__audiomoth-017__20260602T104533Z__chainsaw__evt-00042.wav` | Exact audio filename. |
| `label` | `chainsaw` | One of `background_unknown`, `chainsaw`, `vehicle`, `gunshot`. |
| `event_id` | `evt-00042` | Same value for clips from the same incident. Use `bg-xxxxx` for background clips. |
| `latitude` | `-12.83421` | Decimal degrees; precision within 50 m required. |
| `longitude` | `-69.29318` | Decimal degrees; precision within 50 m required. |
| `gps_accuracy_m` | `12` | Estimated GPS accuracy in meters. |
| `local_date` | `2026-06-02` | Local recording date. |
| `local_time` | `05:45:33` | Local recording start time, 24-hour clock. |
| `timezone` | `America/Lima` | IANA timezone or fixed UTC offset. |
| `utc_start_time` | `2026-06-02T10:45:33Z` | UTC recording start time. |
| `duration_seconds` | `30` | File duration or event duration. |
| `event_start_seconds` | `4.2` | Use `0` for a clip that starts at the event. |
| `event_end_seconds` | `24.8` | Use the file duration for full-clip labels. |
| `device_type` | `AudioMoth 1.2.0` | Device model. |
| `sample_rate_hz` | `48000` | Actual sample rate. |
| `file_format` | `wav` | `wav` or `flac` preferred. |
| `annotator` | `ranger-a.singh` | Person who verified the label. |
| `annotation_status` | `verified` | Use `verified`, `needs_review`, or `rejected`. Only `verified` rows enter training. |
| `verification_source` | `field_observed` | Example values: `field_observed`, `ranger_report`, `camera_trap_match`, `controlled_safe_test`, `unknown`. |
| `notes` | `distant cutting, light rain` | Free-text context. |

Recommended additional columns:

| Column | Example | Use |
| --- | --- | --- |
| `habitat_type` | `terra_firme_forest` | Helps diagnose site-specific errors. |
| `distance_estimate_m` | `300` | Useful for threat range evaluation. |
| `weather` | `light_rain` | Helps separate threats from rain/wind artifacts. |
| `human_activity_context` | `near_road` | Notes expected non-threat human noise. |
| `vehicle_subtype` | `motorcycle` | Required when known for `vehicle`. |
| `gunshot_count` | `3` | Required when known for `gunshot`. |
| `chainsaw_mode` | `cutting` | Required when known for `chainsaw`. |

Metadata quality rules:

- Every `verified` row must have an annotator.
- Every threat row must have an `event_id`.
- Never reuse an `event_id` for unrelated incidents.
- If the same event is split into several clips, reuse the same `event_id`; Canopy will keep those clips in the same train, validation, or test split.
- Rows marked `needs_review` can be stored but will not be used for training until verified.

## Delivery Package

Deliver data in this folder shape:

```text
canopy-field-audio-<organization_id>-<delivery_date>/
  canopy_audio_metadata.csv
  audio/
    background_unknown/
      *.wav
    chainsaw/
      *.wav
    vehicle/
      *.wav
    gunshot/
      *.wav
```

Minimum viable delivery checklist:

- 3 sites.
- 24 hours of background per site.
- 90 verified chainsaw events across 3 sites.
- 90 verified vehicle events across 3 sites if vehicle alerts are requested.
- 30 verified gunshot events across 2 sites if gunshot alerts are requested.
- `canopy_audio_metadata.csv` with all required columns.
- No tambopata-style imbalance: no single site over 40% of chainsaw or vehicle examples, and no single site over 60% of gunshot examples.

Recommended delivery checklist:

- 8 to 12 sites.
- 72 hours of background per site.
- 240 verified chainsaw events.
- 240 verified vehicle events.
- 120 verified gunshot events.
- All recommended metadata columns filled when known.
- No single site over 40% of any threat class.

## What The Current Model Can And Cannot Do

What it can do today:

- Produce research scores for uploaded audio clips.
- Recognize some chainsaw-like patterns in public rainforest audio.
- Stay suppressed in fusion when confidence is too low, so satellite-only scoring can continue without trusting weak acoustic evidence.
- Help prioritize manual review during research experiments.

What it cannot do today:

- It cannot reliably detect chainsaws at a new forest site.
- It cannot keep false alarms low while also catching enough chainsaws to be deployable.
- It cannot be trusted for gunshot, vehicle, or fire alerts in field conditions.
- It cannot replace ranger judgment, field verification, or incident response protocols.
- It cannot pass the current promotion gate: chainsaw recall above 0.70 and background false positives below 0.10 on a held-out set containing at least 3 sites.

Plain-language status:

The classifier has learned that some recordings sound like chainsaws, but it has not yet learned the difference between "chainsaw" and "this particular forest/site/device sounds like the training data." Field data is needed so the model learns the real operating environment instead of public dataset shortcuts.

## What Happens To Partner Data

Inside the Canopy platform:

- Audio is associated with the partner organization's workspace.
- Raw audio and metadata stay scoped to that organization.
- Data from one organization is not used to train or evaluate another organization's model unless the data owner gives explicit written permission.
- Field data is used for three purposes: quality review, model training, and held-out validation.
- Held-out validation sites are kept separate from training so the partner receives an honest estimate of field performance.
- Reports can include aggregate metrics such as recall, false-positive rate, site counts, and confusion summaries.
- Raw audio is not committed to the public repository.

What the partner receives back:

- A data quality report listing accepted rows, rejected rows, missing metadata, and site/class balance.
- A held-out validation report with chainsaw, vehicle, and gunshot metrics for the classes that have enough verified data.
- A recommendation: keep acoustic confidence suppressed, run a limited research pilot, or promote the org-specific model into fusion scoring if it passes the fixed gate.

Promotion rule:

- Acoustic confidence can re-enter fusion only after the model reaches chainsaw recall above 0.70 and background false-positive rate below 0.10 on held-out clips from at least 3 sites.
- The gate is set before evaluation and does not move based on the model's result.
