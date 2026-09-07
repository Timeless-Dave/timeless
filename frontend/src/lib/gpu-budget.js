/**
 * Decides whether the expensive visual layer should run.
 *
 * This is load shedding, not thermal measurement. The browser exposes no
 * temperature, power draw, or thermal-pressure signal, so nothing here can
 * prove a laptop is hot: a GPU can hold 60fps while drawing serious power.
 * What it can do is stop the expensive layer whenever the cheap proxies say it
 * is probably not worth paying for — on battery, saving data, asked to reduce
 * motion, or visibly dropping frames — and give the owner a switch.
 *
 * Confirming the fan problem still needs a real energy trace on the machine.
 *
 * A single module-level store, so every surface reads one answer and only one
 * frame sampler ever runs.
 */

const STORAGE_KEY = 'timeless_effects_mode';
const SAMPLE_MS = 1800;
// The first sample runs soon after load; a machine that is already struggling
// should not have to wait half a minute for the shader to back off.
const FIRST_SAMPLE_MS = 4000;
const SAMPLE_EVERY_MS = 30000;
// Below roughly 36fps while effects are running, the machine is struggling.
const SLOW_FRAME_MS = 28;
const SLOW_FRAME_SHARE = 0.5;

const listeners = new Set();

function readMode() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored === 'quiet' || stored === 'full' ? stored : 'auto';
  } catch {
    return 'auto';
  }
}

const signals = {
  mode: typeof window === 'undefined' ? 'auto' : readMode(),
  reducedMotion: false,
  saveData: false,
  reducedData: false,
  onBattery: false,
  batteryKnown: false,
  pressure: false,
};

let snapshot = computeSnapshot();

function computeSnapshot() {
  // Reduced motion is an accessibility preference, not a performance hint, so
  // it is checked before the manual switch: "Full" may not override it.
  if (signals.reducedMotion) {
    return {
      quiet: true,
      reason: 'Your system asks for reduced motion.',
      mode: signals.mode,
      pressure: signals.pressure,
    };
  }
  if (signals.mode !== 'auto') {
    const quiet = signals.mode === 'quiet';
    return {
      quiet,
      reason: quiet ? 'Quiet effects are switched on.' : null,
      mode: signals.mode,
      pressure: signals.pressure,
    };
  }
  let quiet = false;
  let reason = null;
  if (signals.pressure) {
    quiet = true;
    reason = 'Frames were dropping, so effects were turned down.';
  } else if (signals.onBattery) {
    // Unplugged at all, not merely nearly flat: the cost of a full-viewport
    // shader is worth avoiding on battery whatever the charge level.
    quiet = true;
    reason = 'Running on battery.';
  } else if (signals.saveData || signals.reducedData) {
    quiet = true;
    reason = 'Data saver is on.';
  }
  return { quiet, reason, mode: signals.mode, pressure: signals.pressure };
}

function publish() {
  const next = computeSnapshot();
  if (
    next.quiet === snapshot.quiet &&
    next.reason === snapshot.reason &&
    next.mode === snapshot.mode &&
    next.pressure === snapshot.pressure
  ) {
    return;
  }
  snapshot = next;
  listeners.forEach(listener => listener());
}

export function getGpuBudget() {
  return snapshot;
}

/** 'auto' | 'full' | 'quiet'. Persisted per browser. */
export function setEffectsMode(mode) {
  signals.mode = ['auto', 'full', 'quiet'].includes(mode) ? mode : 'auto';
  try {
    if (signals.mode === 'auto') window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, signals.mode);
  } catch {
    /* preference is per-browser and optional */
  }
  if (signals.mode !== 'auto') signals.pressure = false;
  publish();
}

let started = false;
const teardown = [];

function watchMedia(query, apply) {
  const mq = window.matchMedia(query);
  apply(mq.matches);
  const handler = () => {
    apply(mq.matches);
    publish();
  };
  mq.addEventListener('change', handler);
  teardown.push(() => mq.removeEventListener('change', handler));
}

/**
 * The Battery API exists only in Chromium. Where it is missing — Safari and
 * Firefox, which is where this dashboard often runs — nothing is assumed: the
 * frame sampler and the manual switch carry the weight instead.
 */
function watchBattery() {
  if (typeof navigator === 'undefined' || !navigator.getBattery) return;
  navigator
    .getBattery()
    .then(battery => {
      const apply = () => {
        signals.batteryKnown = true;
        signals.onBattery = !battery.charging;
        publish();
      };
      apply();
      battery.addEventListener('chargingchange', apply);
      teardown.push(() => battery.removeEventListener('chargingchange', apply));
    })
    .catch(() => {
      /* the API is optional and permission-gated */
    });
}

/**
 * Samples frame timing in short bursts rather than continuously, so the probe
 * for cost is not itself a cost. Latches on the first sustained slowdown: a
 * threshold that flips back and forth would restart the shader repeatedly.
 */
function watchFramePressure() {
  let timer = 0;
  let raf = 0;

  const burst = () => {
    if (signals.mode !== 'auto' || signals.pressure || document.hidden) {
      timer = window.setTimeout(burst, SAMPLE_EVERY_MS);
      return;
    }
    const frames = [];
    let last = performance.now();
    const started = last;
    const step = now => {
      frames.push(now - last);
      last = now;
      if (now - started < SAMPLE_MS) {
        raf = requestAnimationFrame(step);
        return;
      }
      // Ignore the first frames: they include the scheduling of the burst itself.
      const usable = frames.slice(2);
      const slow = usable.filter(delta => delta > SLOW_FRAME_MS).length;
      if (usable.length >= 20 && slow / usable.length >= SLOW_FRAME_SHARE) {
        signals.pressure = true;
        publish();
      }
      timer = window.setTimeout(burst, SAMPLE_EVERY_MS);
    };
    raf = requestAnimationFrame(step);
  };

  timer = window.setTimeout(burst, FIRST_SAMPLE_MS);
  teardown.push(() => {
    window.clearTimeout(timer);
    cancelAnimationFrame(raf);
  });
}

function start() {
  if (started || typeof window === 'undefined') return;
  started = true;
  watchMedia('(prefers-reduced-motion: reduce)', value => {
    signals.reducedMotion = value;
  });
  watchMedia('(prefers-reduced-data: reduce)', value => {
    signals.reducedData = value;
  });
  signals.saveData = Boolean(navigator?.connection?.saveData);
  watchBattery();
  watchFramePressure();
  snapshot = computeSnapshot();
}

export function subscribeGpuBudget(listener) {
  start();
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Test seam: reset every signal and listener. */
export function __resetGpuBudget(overrides = {}) {
  Object.assign(signals, {
    mode: 'auto',
    reducedMotion: false,
    saveData: false,
    reducedData: false,
    onBattery: false,
    batteryKnown: false,
    pressure: false,
    ...overrides,
  });
  snapshot = computeSnapshot();
  return snapshot;
}
