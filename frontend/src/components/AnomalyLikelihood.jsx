// Renders the open-set acoustic detector output: how anomalous a sound is vs
// normal forest background, plus a ranked likelihood of what it seems to be
// (including an honest "unknown" when it matches no known threat prototype).
const KIND_LABELS = {
  chainsaw: 'Chainsaw',
  gunshot: 'Gunshot',
  vehicle: 'Vehicle',
  fire_crackle: 'Fire',
  unknown: 'Unknown',
}

const pct = (value) => `${Math.round((value || 0) * 100)}%`

export default function AnomalyLikelihood({ anomalyScore, isAnomaly, likelihoods }) {
  const entries = Object.entries(likelihoods || {}).sort((a, b) => b[1] - a[1])
  return (
    <div className="anomaly-metadata">
      <p className="anomaly-score-line">
        Anomaly score: <span className="anomaly-score-value">{pct(anomalyScore)}</span>
        <span className="anomaly-subtle">
          {isAnomaly === false ? ' · within normal background' : ' · vs normal forest background'}
        </span>
      </p>
      {entries.length > 0 && (
        <div className="likelihood-list">
          <p className="likelihood-heading">Likely source</p>
          {entries.map(([label, prob]) => (
            <div className="likelihood-row" key={label}>
              <span className={`likelihood-label${label === 'unknown' ? ' unknown' : ''}`}>
                {KIND_LABELS[label] || label}
              </span>
              <div className="likelihood-bar-bg">
                <div
                  className={`likelihood-bar-fill${label === 'unknown' ? ' unknown' : ''}`}
                  style={{ width: pct(prob) }}
                />
              </div>
              <span className="likelihood-pct">{pct(prob)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
