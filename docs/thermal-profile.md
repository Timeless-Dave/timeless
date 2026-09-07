# Measuring the MacBook heat

The effects budget in `frontend/src/lib/gpu-budget.js` is load shedding against
cheap proxies. It is not evidence about what is heating the machine, and it
cannot be: the browser exposes no temperature, power draw, or thermal-pressure
signal, and a GPU can hold 60fps while drawing serious power.

This is the protocol that would settle it. It needs a real browser on the real
machine, so it has to be run by hand.

**Automation helpers** (repo root):

```bash
# One mode: opens Chromium on the dashboard + samples SMC every 60s for 10 min
./scripts/thermal-profile.sh quiet   # also: auto, full, baseline

# Full protocol (3 runs + cooldown between)
./scripts/thermal-session.sh

# Browser only (from frontend/)
pnpm exec node scripts/thermal-browser.mjs quiet 10
```

Logs land in `docs/thermal-runs/`. `powermetrics` requires `sudo`.

## Setup

1. Quit everything else. Close other browser windows and other apps; a single
   Chrome window on the dashboard is the only thing that should be running.
2. Plug in and let the machine sit for five minutes so it starts cool. Note the
   starting fan speed and temperature (`sudo powermetrics --samplers smc -i1 -n1`
   reports fan RPM and CPU die temperature).
3. Serve the built app the way it normally runs, not the Vite dev server:
   `pnpm build` in `frontend/`, then start the service as usual.
4. Open the dashboard and leave it in the foreground, untouched.

## The three runs

Set the effects mode in the Theme popover, then leave the page alone for a full
ten minutes. Do this three times, letting the machine settle back to its
starting temperature between runs.

| Run | Effects mode |
|-----|--------------|
| 1   | Quiet        |
| 2   | Auto         |
| 3   | Full         |

For each run record:

- **Fan RPM and CPU die temperature** at 0, 5 and 10 minutes:
  `sudo powermetrics --samplers smc -i 60000 -n 11 | grep -E "Fan|die temperature"`
- **Per-process CPU and GPU**: Activity Monitor, Energy tab, "Energy Impact"
  and "12 hr Power" for the browser process and for the Python service. The GPU
  tab shows GPU time per process.
- **Browser-side frames and memory**: Chrome DevTools, Performance monitor
  (Cmd-Shift-P, "Show performance monitor"): CPU usage, JS heap size, DOM node
  count, and layouts/sec. Watch whether the heap or node count grows over ten
  minutes — a leak looks like a slope, not a level.

## Reading the result

- **Full is hot, Quiet is cool.** The shader is the cause. Make Quiet the
  default in `gpu-budget.js` (change the `auto` branch to start quiet) and
  restore effects deliberately, one at a time, remeasuring each.
- **Quiet is still hot.** The visual layer is not the cause and the budget is
  treating a symptom. Look next at, in order of likelihood:
  - the 60-second `/api/today` poll in `TodayContext.jsx`, which re-renders the
    whole dashboard and re-runs every summary calculation;
  - the launchd collectors in `macos/launchd/` — ActivityWatch, screenpipe and
    the mail and calendar ingests all run outside the browser and none of them
    are throttled by anything in this repo;
  - the Python service itself, which opens a SQLite connection per request path
    and recomputes `productivity_on_day` on every `/api/today`.
  Activity Monitor's per-process split tells you which of the three it is
  before you change any code.
- **Auto tracks Quiet.** The automatic signals are firing correctly and no
  further work is needed beyond making sure Auto stays the default.

Record the numbers somewhere durable. Without them, any further change to the
visual layer is a guess.
