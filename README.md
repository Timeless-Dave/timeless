# Timeless

Local personal assistant for a MacBook and a Samsung phone. Personal use. **$0**.

Spec: [`docs/superpowers/specs/2026-08-15-timeless-design.md`](docs/superpowers/specs/2026-08-15-timeless-design.md)

## On this Mac (already set up)

| Piece | Status |
|---|---|
| Timeless brain | LaunchAgent `com.timeless.brain` → http://127.0.0.1:8787 |
| Full-screen gate/halt overlay | LaunchAgent `com.timeless.overlay` |
| ActivityWatch | `/Applications/ActivityWatch.app` + login item, API `:5600` |
| AW → Timeless ingest | LaunchAgent `com.timeless.aw-ingest` every 2 minutes |
| Ollama | `brew services` + model `qwen2.5:7b` |
| Screenpipe (personal binary) | LaunchAgent `com.timeless.screenpipe` — screen OCR, no mic |
| Screenpipe → Timeless | LaunchAgent `com.timeless.sp-ingest` every 3 minutes |
| Android APK | `~/Library/Application Support/Timeless/installers/aw-android.apk` |

Phone install when USB is connected:

```bash
./scripts/install-phone.sh
```

Reinstall login services after a pull:

```bash
./scripts/install-launchd.sh
```

## You still have to click (macOS will not allow this unattended)

1. **ActivityWatch** → System Settings → Privacy & Security → **Accessibility** (and Screen Recording if asked). Without this, window titles stay empty.
2. Chrome extension [ActivityWatch Web Watcher](https://chromewebstore.google.com/detail/activitywatch-web-watcher) so job URLs reach Timeless.
3. **Now (USB):** Developer options + USB debugging on the Samsung, plug into this Mac, allow the RSA prompt, then run `./scripts/install-phone.sh`. Then Usage Access ON and battery optimization OFF for ActivityWatch.
4. Overlay: first launch may ask to allow network / Accessibility. Keep it.

## Screenpipe (pixels on the Mac)

Personal build is already at `~/Library/Application Support/Timeless/bin/screenpipe` (not the paid app). `install-launchd.sh` starts `screenpipe record --disable-audio`. Approve Screen Recording if macOS asks again.

Rebuild later with `./scripts/build-screenpipe.sh`.

## Mail / Tailscale / calendar

Calendar.app (EventKit) and Mail.app ingest on a timer. Allow Calendar and Automation when macOS asks. Dashboard: http://127.0.0.1:8787 — Chicago timezone, nightly recap overlay at 23:55.

Phone: brain binds `0.0.0.0:8787` with a token (loopback is open). Copy the LAN/Tailscale URL from Sensors. Overlay stays on localhost and **does not use the Dock** (agent policy).

**Halt on phone:** every 2 minutes the phone pull job checks for an active halt. If one exists, it posts an Android notification and opens `/halt` in the phone browser (same token as Sensors). Wireless ADB must be connected.

**Escalation ladder (no Twilio):** `com.timeless.halt-escalate` runs every 60s. Unacked halts ping the phone at +2m, +5m (opens `/halt`), +10m (louder alarm). Skipped during Focus quiet/dormant.

**Focus / Panic:** Dashboard **Focus** button sets quiet/mild/dormant for 15m–2h. **Panic** on the halt screen sets dormant for 1 hour. Interview events auto-enable quiet ±5 minutes around the calendar block.

Wireless ADB after reboot: in `~/Library/Application Support/Timeless/phone-adb.conf` set `ADB_PAIR_HOST`, `ADB_PAIR_PORT`, `ADB_PAIR_CODE` from Wireless debugging → Pair with pairing code. The pull job retries connect + mDNS.

Chrome URLs: `./scripts/install-chrome-aw.sh` then click Add.

## Dev

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
## Google Sheets tracker

Timeless is the source of truth for internships, conferences, hackathons, and other programs. Google Sheets is an explicit publish target: syncing replaces the dedicated `Tracker` worksheet, so spreadsheet edits cannot silently overwrite local data.

1. Enable the Google Sheets API and create a **Web application** OAuth client.
2. Add `http://127.0.0.1:8787/oauth/google/callback` as an authorized redirect URI.
3. Store the rotated credentials outside the repository (the prompt hides the secret):

   ```sh
   ./scripts/configure-google.sh
   ```

4. Restart Timeless, open **Programs**, and select **Connect Sheets**.

OAuth client configuration and tokens are stored separately under `~/Library/Application Support/Timeless/`, both with owner-only permissions. Environment variables remain supported for deployments. The app requests only the Google Sheets scope. **Sync** creates the tracker on first use and reuses it afterward; **View sheet** opens it, and **Export CSV** remains available as a fallback.

### Smart capture and reminders

- **Browser:** ActivityWatch forwards recent browser activity, but Timeless retains only strong internship/job, hackathon, and conference matches. It does not import the browser's full history. Tracking parameters and fragments are removed before deduplication.
- **Mail:** the Mail.app ingest scans a bounded set of recent inbox messages, classifies their subject plus a bounded body excerpt, and extracts relevant program links, dates, interview links, rejections, and application confirmations.
- **Calendar:** calendar events remain the authority for event time and location. Conferences and hackathons are also promoted into Programs; interview events receive join/leave reminders and automatic quiet time.
- **Deadlines:** tracked program deadlines create staged reminders at seven days, one day, and four hours. They never become check-in meetings.
- **Sheets:** every Programs record is published to the dedicated Tracker worksheet. Timeless stays authoritative so spreadsheet edits cannot silently overwrite newer local state.

### Productivity and plan alignment

ActivityWatch window/web samples are deduplicated by source ID and overlapping intervals are merged before scoring. Timeless stores the app, hostname, bounded title, category, and duration—not full page URLs or page contents. Each interval is classified as plan-aligned productive work, productive but off-plan, distracting, or unknown. Unknown time is shown as coverage and is never scored as failure.

The estimate weights plan-aligned work fully, productive off-plan work partially, and distracting work at zero. The dashboard always shows the underlying minutes and recent evidence alongside the score. Classification is deliberately local and deterministic, so it can be audited and tuned without sending activity history to an external model.

### Semester courses

Semester-scoped course data lives in `config/academics/`. The Fall 2026 configuration contains the six verified courses from the Workday schedule, meeting locations/times, no-class dates, and a curated set of student-relevant UAPB academic dates. It deliberately excludes the student identifier from the source PDF.

The daily gate and dashboard plan editor expose horizontal preset chips for Code, LeetCode, Coursera, Algorithms, applications, study activities, and current courses. **Add to Calendar** performs an idempotent EventKit sync: rerunning it updates Timeless-owned events by stable academic UID rather than creating duplicates. Regular classes receive a 15-minute reminder; academic deadlines receive staged reminders; informational dates and breaks remain non-blocking calendar entries.
