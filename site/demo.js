/* Canopy in-browser detector demo.
 *
 * Mirrors research/audio exactly:
 *   audio -> 16 kHz mono, 4 s center crop/pad
 *         -> log-mel (n_fft 1024, hop 320, 64 mels, hann, reflect pad, power 2)
 *         -> log(mel + 1e-6), per-clip standardize (unbiased std, like torch)
 *         -> CNN (ONNX) -> 64-d embedding
 *         -> Mahalanobis vs forest-background Gaussian -> quantile anomaly score
 *         -> cosine-to-prototype open-set likelihoods
 */

(() => {
  const $ = id => document.getElementById(id);
  const clipList = $('clip-list');
  if (!clipList) return;

  const SR = 16000;
  const N = 64000;          // 4 s
  const NFFT = 1024;
  const HOP = 320;
  const NMELS = 64;
  const FRAMES = Math.floor(N / HOP) + 1;   // 201, torch center=true

  let detector = null;      // detector.json
  let melFb = null;         // Float32Array (513 * 64)
  let session = null;       // ort session
  let clips = [];
  let audioCtx = null;
  let busy = false;

  const status = msg => { $('demo-status').textContent = msg; };

  /* ---------------- assets ---------------- */

  // HTK-scale mel filterbank, identical to torchaudio melscale_fbanks
  // (f_min 0, f_max sr/2, norm None, mel_scale "htk"); n_freqs x n_mels
  function buildMelFb(nFreqs) {
    const fMax = SR / 2;
    const hzToMel = f => 2595 * Math.log10(1 + f / 700);
    const melToHz = m => 700 * (Math.pow(10, m / 2595) - 1);
    const mMax = hzToMel(fMax);
    const fPts = new Float64Array(NMELS + 2);
    for (let i = 0; i < NMELS + 2; i++) fPts[i] = melToHz((mMax * i) / (NMELS + 1));
    const fb = new Float32Array(nFreqs * NMELS);
    for (let f = 0; f < nFreqs; f++) {
      const freq = (fMax * f) / (nFreqs - 1);
      for (let m = 0; m < NMELS; m++) {
        const up = (freq - fPts[m]) / (fPts[m + 1] - fPts[m]);
        const down = (fPts[m + 2] - freq) / (fPts[m + 2] - fPts[m + 1]);
        fb[f * NMELS + m] = Math.max(0, Math.min(up, down));
      }
    }
    return fb;
  }

  const hann = new Float32Array(NFFT);
  for (let i = 0; i < NFFT; i++) hann[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / NFFT);

  async function loadAssets() {
    if (session) return;
    status('LOADING MODEL AND BASELINE ...');
    detector = await fetch('demo/detector.json').then(r => r.json());
    melFb = buildMelFb(NFFT / 2 + 1);
    if (typeof ort === 'undefined') throw new Error('onnxruntime failed to load');
    ort.env.wasm.numThreads = 1;
    session = await ort.InferenceSession.create('demo/model.onnx', {
      executionProviders: ['wasm'],
    });
    status('MODEL RESIDENT · ' + detector.embedder_version.toUpperCase() + ' · LOCAL ONLY');
  }

  /* ---------------- audio -> samples ---------------- */

  function ctx() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    return audioCtx;
  }

  async function decodeToMono16k(arrayBuffer) {
    // decodeAudioData resamples to the context rate, so decoding inside a
    // 16 kHz offline context needs no second resampling pass
    const off = new OfflineAudioContext(1, 1, SR);
    const decoded = await off.decodeAudioData(arrayBuffer.slice(0));
    if (decoded.numberOfChannels === 1) return decoded.getChannelData(0);
    const out = new Float32Array(decoded.length);
    for (let c = 0; c < decoded.numberOfChannels; c++) {
      const ch = decoded.getChannelData(c);
      for (let i = 0; i < out.length; i++) out[i] += ch[i] / decoded.numberOfChannels;
    }
    return out;
  }

  function centerCrop(samples) {
    const out = new Float32Array(N);
    if (samples.length >= N) {
      const start = Math.floor((samples.length - N) / 2);
      out.set(samples.subarray(start, start + N));
    } else {
      out.set(samples);
    }
    return out;
  }

  /* ---------------- FFT (iterative radix-2, complex) ---------------- */

  const fftRe = new Float32Array(NFFT);
  const fftIm = new Float32Array(NFFT);
  const rev = new Uint16Array(NFFT);
  {
    const bits = Math.log2(NFFT);
    for (let i = 0; i < NFFT; i++) {
      let r = 0;
      for (let b = 0; b < bits; b++) r = (r << 1) | ((i >> b) & 1);
      rev[i] = r;
    }
  }
  const cosT = new Float32Array(NFFT / 2);
  const sinT = new Float32Array(NFFT / 2);
  for (let i = 0; i < NFFT / 2; i++) {
    cosT[i] = Math.cos((-2 * Math.PI * i) / NFFT);
    sinT[i] = Math.sin((-2 * Math.PI * i) / NFFT);
  }

  function fftPower(frame, out) {
    for (let i = 0; i < NFFT; i++) {
      fftRe[i] = frame[rev[i]];
      fftIm[i] = 0;
    }
    for (let size = 2; size <= NFFT; size <<= 1) {
      const half = size >> 1;
      const step = NFFT / size;
      for (let base = 0; base < NFFT; base += size) {
        for (let k = 0; k < half; k++) {
          const tw = k * step;
          const i0 = base + k, i1 = base + k + half;
          const tr = fftRe[i1] * cosT[tw] - fftIm[i1] * sinT[tw];
          const ti = fftRe[i1] * sinT[tw] + fftIm[i1] * cosT[tw];
          fftRe[i1] = fftRe[i0] - tr;
          fftIm[i1] = fftIm[i0] - ti;
          fftRe[i0] += tr;
          fftIm[i0] += ti;
        }
      }
    }
    for (let k = 0; k <= NFFT / 2; k++) {
      out[k] = fftRe[k] * fftRe[k] + fftIm[k] * fftIm[k];
    }
  }

  /* ---------------- log-mel ---------------- */

  function logMel(samples) {
    const window = hann;
    const nFreqs = NFFT / 2 + 1;                // 513
    const pad = NFFT / 2;
    // reflect padding, like torch.stft(center=True)
    const padded = new Float32Array(N + NFFT);
    for (let i = 0; i < pad; i++) padded[i] = samples[pad - i];
    padded.set(samples, pad);
    for (let i = 0; i < pad; i++) padded[pad + N + i] = samples[N - 2 - i];

    const mel = new Float32Array(NMELS * FRAMES);  // row-major (mel, frame)
    const frame = new Float32Array(NFFT);
    const power = new Float32Array(nFreqs);
    for (let t = 0; t < FRAMES; t++) {
      const off = t * HOP;
      for (let i = 0; i < NFFT; i++) frame[i] = padded[off + i] * window[i];
      fftPower(frame, power);
      for (let m = 0; m < NMELS; m++) {
        let acc = 0;
        for (let f = 0; f < nFreqs; f++) acc += power[f] * melFb[f * NMELS + m];
        mel[m * FRAMES + t] = Math.log(acc + detector.audio.log_offset);
      }
    }
    // standardize (torch: mean over all, unbiased std)
    let mean = 0;
    for (let i = 0; i < mel.length; i++) mean += mel[i];
    mean /= mel.length;
    let varSum = 0;
    for (let i = 0; i < mel.length; i++) varSum += (mel[i] - mean) ** 2;
    const std = Math.max(Math.sqrt(varSum / (mel.length - 1)), 1e-6);
    for (let i = 0; i < mel.length; i++) mel[i] = (mel[i] - mean) / std;
    return mel;
  }

  /* ---------------- detector math ---------------- */

  function mahalanobis(emb) {
    const d = emb.length;
    const mean = detector.background.mean;
    const ic = detector.background.inv_cov;
    const c = new Float64Array(d);
    for (let i = 0; i < d; i++) c[i] = emb[i] - mean[i];
    let quad = 0;
    for (let i = 0; i < d; i++) {
      let row = 0;
      for (let j = 0; j < d; j++) row += ic[i * d + j] * c[j];
      quad += c[i] * row;
    }
    return Math.sqrt(Math.max(quad, 0));
  }

  function quantileScore(distance) {
    // levels are linspace(0, 1, N), so level[i] = i / (N - 1)
    const qd = detector.background.quantile_distances;
    const last = qd.length - 1;
    if (distance <= qd[0]) return 0;
    if (distance >= qd[last]) return 1;
    let lo = 0, hi = last;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (qd[mid] <= distance) lo = mid; else hi = mid;
    }
    const span = qd[hi] - qd[lo];
    const t = span > 0 ? (distance - qd[lo]) / span : 0;
    return (lo + t) / last;
  }

  function likelihoods(emb) {
    const labels = detector.prototypes.labels;
    const d = emb.length;
    if (!labels.length) return { unknown: 1 };
    let norm = 0;
    for (let i = 0; i < d; i++) norm += emb[i] * emb[i];
    norm = Math.max(Math.sqrt(norm), 1e-12);
    const sims = labels.map((_, p) => {
      let acc = 0;
      for (let i = 0; i < d; i++) acc += detector.prototypes.vectors[p * d + i] * (emb[i] / norm);
      return acc;
    });
    const maxSim = Math.max(...sims);
    const denom = Math.max(1 - detector.sim_threshold, 1e-6);
    const known = Math.min(Math.max((maxSim - detector.sim_threshold) / denom, 0), 1);
    const temp = Math.max(detector.temperature, 1e-6);
    const shifted = sims.map(s => Math.exp((s - maxSim) / temp));
    const sum = shifted.reduce((a, b) => a + b, 0);
    const out = {};
    labels.forEach((label, i) => { out[label] = known * (shifted[i] / sum); });
    out.unknown = 1 - known;
    return out;
  }

  /* ---------------- scoring ---------------- */

  async function scoreSamples(samples, sourceName) {
    const mel = logMel(samples);
    drawSpec(mel);
    const input = new ort.Tensor('float32', mel, [1, 1, NMELS, FRAMES]);
    const out = await session.run({ log_mel: input });
    const emb = out.embedding.data;
    const distance = mahalanobis(emb);
    const score = quantileScore(distance);
    const lik = likelihoods(emb);
    render(score, lik);
    console.log('[canopy-demo]', sourceName, {
      anomaly_score: +score.toFixed(4),
      distance: +distance.toFixed(4),
      likelihoods: Object.fromEntries(Object.entries(lik).map(([k, v]) => [k, +v.toFixed(4)])),
    });
    return { score, lik };
  }

  /* ---------------- rendering ---------------- */

  function drawSpec(mel) {
    const canvas = $('spec-canvas');
    const c = canvas.getContext('2d');
    const img = c.createImageData(FRAMES, NMELS);
    let lo = Infinity, hi = -Infinity;
    for (const v of mel) { if (v < lo) lo = v; if (v > hi) hi = v; }
    const span = Math.max(hi - lo, 1e-9);
    for (let m = 0; m < NMELS; m++) {
      for (let t = 0; t < FRAMES; t++) {
        const v = (mel[m * FRAMES + t] - lo) / span;             // 0..1
        const i = ((NMELS - 1 - m) * FRAMES + t) * 4;            // low freq at bottom
        img.data[i] = 12 + v * (v > 0.75 ? 220 : 130);
        img.data[i + 1] = 12 + v * 150;
        img.data[i + 2] = 10 + v * 95;
        img.data[i + 3] = 255;
      }
    }
    c.putImageData(img, 0, 0);
  }

  function render(score, lik) {
    const flagged = score >= detector.background.anomaly_score_threshold;
    $('score-num').textContent = score.toFixed(3);
    $('score-cap').textContent =
      'MORE UNUSUAL THAN ' + Math.round(score * 100) + '% OF FOREST BACKGROUND';
    const verdict = $('verdict');
    verdict.textContent = flagged ? 'FLAGGED FOR REVIEW'
      : score >= 0.75 ? 'ELEVATED · WATCHING'
      : 'WITHIN BASELINE';
    verdict.className = 'verdict ' + (flagged ? 'v-flag' : score >= 0.75 ? 'v-warn' : 'v-ok');
    const fill = $('meter-fill');
    fill.style.width = (score * 100).toFixed(1) + '%';
    fill.className = 'meter-fill ' + (flagged ? 'v-flag' : score >= 0.75 ? 'v-warn' : 'v-ok');

    const order = Object.entries(lik).sort((a, b) => b[1] - a[1]);
    $('likelihoods').innerHTML = order.map(([label, value]) => `
      <div class="lik-row${label === 'unknown' ? ' lik-unknown' : ''}">
        <span class="lik-label">${label.replace('_', ' ').toUpperCase()}</span>
        <span class="lik-bar"><i style="width:${(value * 100).toFixed(1)}%"></i></span>
        <span class="lik-val">${value.toFixed(2)}</span>
      </div>`).join('');
  }

  /* ---------------- inputs ---------------- */

  async function runArrayBuffer(buf, sourceName) {
    if (busy) return;
    busy = true;
    try {
      await loadAssets();
      status('ANALYSING ...');
      const samples = centerCrop(await decodeToMono16k(buf));
      await scoreSamples(samples, sourceName);
      status('DONE · MODEL RAN LOCALLY · NOTHING LEFT THIS TAB');
    } catch (err) {
      console.error(err);
      status('ERROR: ' + err.message);
    } finally {
      busy = false;
    }
  }

  let playing = null;
  function playBuffer(arrayBuffer) {
    ctx().decodeAudioData(arrayBuffer.slice(0)).then(decoded => {
      if (playing) playing.stop();
      const src = ctx().createBufferSource();
      src.buffer = decoded;
      src.connect(ctx().destination);
      src.start();
      playing = src;
    });
  }

  async function buildClipList() {
    clips = await fetch('demo/clips.json').then(r => r.json());
    clipList.innerHTML = clips.map((clip, i) => `
      <button class="clip-row" data-i="${i}">
        <span class="clip-idx">${String(i + 1).padStart(2, '0')}</span>
        <span class="clip-body">
          <span class="clip-title">${clip.title}</span>
          <span class="clip-story">${clip.story}</span>
        </span>
        <span class="clip-run">RUN</span>
      </button>`).join('');
    clipList.querySelectorAll('.clip-row').forEach(row => {
      row.addEventListener('click', async () => {
        clipList.querySelectorAll('.clip-row').forEach(r => r.classList.remove('active'));
        row.classList.add('active');
        const clip = clips[+row.dataset.i];
        const buf = await fetch('demo/' + clip.file).then(r => r.arrayBuffer());
        playBuffer(buf);
        await runArrayBuffer(buf, clip.name);
      });
    });
  }

  $('file-input').addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    clipList.querySelectorAll('.clip-row').forEach(r => r.classList.remove('active'));
    runArrayBuffer(await file.arrayBuffer(), file.name);
  });

  $('btn-mic').addEventListener('click', async () => {
    if (busy) return;
    const btn = $('btn-mic');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const parts = [];
      rec.ondataavailable = e => parts.push(e.data);
      const done = new Promise(resolve => { rec.onstop = resolve; });
      rec.start();
      for (let s = 4; s > 0; s--) {
        btn.textContent = 'RECORDING ... ' + s;
        await new Promise(r => setTimeout(r, 1000));
      }
      rec.stop();
      await done;
      stream.getTracks().forEach(t => t.stop());
      btn.textContent = 'RECORD 4 S FROM MIC';
      clipList.querySelectorAll('.clip-row').forEach(r => r.classList.remove('active'));
      const buf = await new Blob(parts).arrayBuffer();
      await runArrayBuffer(buf, 'microphone');
    } catch (err) {
      btn.textContent = 'RECORD 4 S FROM MIC';
      status('MIC UNAVAILABLE: ' + err.message);
    }
  });

  buildClipList();

  /* Optional self-test: ?selftest runs every bundled clip and compares against
     the Python reference scores stored in clips.json. */
  if (location.search.includes('selftest')) {
    (async () => {
      await loadAssets();
      for (const clip of clips) {
        const buf = await fetch('demo/' + clip.file).then(r => r.arrayBuffer());
        const samples = centerCrop(await decodeToMono16k(buf));
        const { score } = await scoreSamples(samples, clip.name);
        const ref = clip.reference.anomaly_score;
        console.log('[selftest]', clip.name,
          'js=' + score.toFixed(4), 'py=' + ref.toFixed(4),
          Math.abs(score - ref) < 0.02 ? 'MATCH' : 'MISMATCH');
      }
      console.log('[selftest] complete');
    })();
  }
})();
