---
name: Timeless
description: An experimental kinetic personal operating system staged as a dimensional dark command field on warm ground.
colors:
  warm-ground: "#f5f2ed"
  warm-shell: "#fffcf8"
  glass-white: "#ffffff"
  command-field: "#303030"
  command-deep: "#17191e"
  command-mid: "#2f3034"
  command-inner: "#4a4949"
  body-ink: "#383838"
  muted-ink: "#6a6969"
  structural-line: "#e8e7e7"
  signal-amber: "#d08726"
  amber-light: "#f8debd"
  cyan-light: "#67e8f9"
  mint-signal: "#d6ffdd"
  cyan-signal: "#d0fbff"
  rose-signal: "#fbf0f3"
  danger: "#e95d5c"
typography:
  display:
    fontFamily: '"Geist Variable", "Mulish", ui-sans-serif, system-ui, sans-serif'
    fontSize: "clamp(3rem, 12vw, 8rem)"
    fontWeight: 800
    lineHeight: 0.95
    letterSpacing: "-0.04em"
  headline:
    fontFamily: '"Geist Variable", "Mulish", ui-sans-serif, system-ui, sans-serif'
    fontSize: "clamp(20px, 2.6vw, 38px)"
    fontWeight: 650
    lineHeight: 1.08
    letterSpacing: "-0.035em"
  title:
    fontFamily: '"Mulish", ui-sans-serif, system-ui, sans-serif'
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.25
  body:
    fontFamily: '"Mulish", ui-sans-serif, system-ui, sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: '"Mulish", ui-sans-serif, system-ui, sans-serif'
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1.45
    letterSpacing: "0.12em"
rounded:
  chip: "8px"
  control: "12px"
  card: "14px"
  glass: "16px"
  shell: "22px"
  stage: "28px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  xxl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.command-field}"
    textColor: "{colors.glass-white}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "8.8px 16px"
  button-glass:
    backgroundColor: "rgba(255,255,255,.1)"
    textColor: "{colors.glass-white}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "8.8px 16px"
  card:
    backgroundColor: "{colors.glass-white}"
    textColor: "{colors.body-ink}"
    rounded: "{rounded.card}"
    padding: "20px 21.6px"
  signal-glass:
    backgroundColor: "rgba(255,255,255,.09)"
    textColor: "{colors.glass-white}"
    rounded: "{rounded.glass}"
    padding: "18px"
  nav-pill:
    backgroundColor: "{colors.glass-white}"
    textColor: "{colors.command-field}"
    typography: "{typography.body}"
    rounded: "{rounded.pill}"
    height: "42px"
---

# Design System: Timeless

## Overview

**Creative North Star: “Kinetic Command Field”**

Timeless is an experimental personal operating system: a dark, spatial command field mounted inside a warm, tactile shell. Light bends across glass, particles assemble into language, navigation blooms under the pointer, and operational signals occupy distinct depths while information remains direct and usable.

This is deliberately high-variance and high-motion (variance 9, motion 9, density 7), but the field surrounds the work rather than preceding it. React Bits components are authored language where they carry meaning: Lightfall, SideRays, Cubes, InfiniteSpiral, Masonry, Folder, EvilEye, ClickSpark, GlowCursor, and BentoAnalytics each retain a role. Motion, canvas, OGL, and shaders always yield to reduced-motion settings, missing WebGL, constrained devices, and semantic fallbacks.

The dashboard's first viewport is the exception and answers to Product Principle 1 alone: it opens on the Now panel — current goal, its completion controls, the current time block, the next event, and evidence freshness — with no branding stage, typed status, or duplicate shortcut layer in front of it. ParticleText, TextType, TrueFocus, GlassJumper, and CommandBlock remain in the component library for ceremonial surfaces such as the daily gate, and are no longer mounted on the dashboard.

**Key Characteristics:**

- Warm mineral ground framing a near-black dimensional command environment.
- Refractive glass with translucent fills, bright edge catches, blur, and spatial overlap.
- Particle typography, shader light, GSAP choreography, and responsive pointer effects.
- Dense operational bento content and a spatial live-signal panel.
- Desktop pill navigation and a compact GSAP-driven mobile menu.
- Visible focus, reduced-motion parity, and graceful WebGL/canvas fallbacks.

## Colors

Warm neutrals establish the physical room; charcoal and graphite create the command field; amber is the system signal, with cyan as emitted light and pastels reserved for semantic state.

### Primary

- **Signal Amber** (`#d08726`): Active energy, focus borders, particle highlights, rays, ripples, and decisive status.
- **Command Field** (`#303030`): Navigation chassis, primary controls, sensor surfaces, and the base dark plane.

### Secondary

- **Cyan Light** (`#67e8f9`): Cursor glow and optical contrast; use as illumination, not a competing brand color.
- **Amber Light** (`#f8debd`): Warm ray pairing, glass labels, and softened signal context.
- **Mint, Cyan, and Rose Signals:** Semantic success, information, and risk states in dense operational regions.

### Neutral

- **Warm Ground / Warm Shell:** `#f5f2ed` outside and `#fffcf8` inside make the dark world feel dimensional rather than generically dark-mode.
- **Command Deep / Mid:** `#17191e` and `#2f3034` define the stage gradient and receding planes.
- **Glass White:** White at controlled alpha supplies refraction, edge light, text, and inset highlights.
- **Body / Muted Ink:** `#383838` and `#6a6969` support conventional reading surfaces outside the dark field.

**The Emitted-Light Rule.** Amber and cyan look like light sources or live signals; never spread them uniformly across static surfaces.

## Typography

**Display Font:** Geist Variable with Mulish and system fallbacks  
**Body Font:** Mulish with system fallbacks  
**Label/Mono Font:** Mulish for labels; system monospace for commands

**Character:** Display type is large, compressed, and capable of becoming animated material. Operational copy stays familiar and highly legible so experimentation never obscures state or action.

### Hierarchy

- **Particle Display:** Extra-bold, up to `clamp(3rem, 12vw, 8rem)`, assembled in canvas particles; keep a semantic text equivalent.
- **Stage Statement:** `clamp(20px, 2.6vw, 38px)`, weight 650, tight leading and tracking.
- **Title:** 20px bold for panels and operational groupings.
- **Body:** 16px at 1.45 for controls, descriptions, and data.
- **Label:** 12px bold with `0.12em` tracking, often uppercase for live metadata only.

**The Material-Type Rule.** Animate typography when it is a focal object—particle gathering, typing, or focus tracking—not for routine paragraphs or dense data.

## Layout

The app occupies a bounded 1440px shell on warm ground. Its core is intentionally asymmetric: the operational stream sits beside a narrower dark sensor rail. The stream opens with the Now panel, followed by four at-a-glance metrics, the activity-evidence card, the plan editor, and then the operational sections. Trends sit behind an explicit disclosure at the end, because they describe the day rather than advance it. Bento spans, masonry, folders, and spiral media create controlled density without equalizing every module.

PillNav is the single navigation system; every destination it names is a section that exists, and its active item follows the section in view rather than the last click. Desktop navigation is a sticky 42px pill assembly with animated logo and circular hover reveals. At 768px it becomes a logo-and-hamburger system with a rounded dynamic menu. At 1100px multi-column content stacks. Touch targets, safe-area clearance, readable flow, and freedom from horizontal overflow remain mandatory.

## Elevation & Depth

Depth is structural and optical. The stage uses radial plus linear dark gradients, a large ambient shadow, isolation, and nested planes. Glass uses translucent white, backdrop blur/saturation, bright one-pixel borders, inset highlights, and selective overlap. OGL Lightfall and SideRays provide environmental illumination; card shadows stay softer so operational content does not compete.

### Shadow Vocabulary

- **Stage Ambient** (`0 34px 90px rgba(25,24,23,.28)`): Grounds the command field.
- **Spatial Signal** (`0 18px 55px rgba(0,0,0,.24), inset 0 1px 0 rgba(255,255,255,.25)`): Lifts the live-signal glass plate.
- **Shell Ambient** (`0 18px 70px rgba(61,50,36,.08)`): Separates warm shell and mineral canvas.
- **Operational Card** (`0 1px 50px rgba(0,0,0,.08)`): Gentle depth for persistent content.

**The Depth-Cue Rule.** Every blur, shadow, ray, or rotation must clarify foreground, atmosphere, or interaction—not merely add gloss.

## Shapes

Geometry shifts with depth: 28px for the stage, 22px for the shell, 16px for floating glass, 14px for cards, 12px for controls, and full pills for navigation. Circles belong to cursor energy, nav reveals, logo controls, particles, and ripple systems. A slight two-degree rotation may mark a spatially floating plate; routine data surfaces remain aligned.

## Components

### Buttons

- **Primary:** Charcoal with white text, 12px corners, compact padding, and tactile response.
- **Glass:** Translucent white on the dark stage with blur and a bright border.
- **Hover / Focus:** Motion may scale, translate, ripple, spark, or reveal color. Keyboard focus keeps the explicit three-pixel amber halo and never relies on animation alone.

### Cards / Containers

- **Operational cards:** White, 14px corners, structural border, readable density, and soft depth.
- **Glass containers:** Alpha-white fill, 16px corners, blur/saturation, edge highlight, and contextual overlap.
- **Bento:** Unequal spans communicate priority. Preserve animated BentoAnalytics rather than flattening it into generic equal cards.

### Navigation

Desktop uses the complete PillNav behavior: circular hover expansion, stacked label transition, active marker, animated logo, and initial reveal. Mobile uses its circular hamburger transformation and rounded popover. Reduced motion presents the same states immediately.

### Kinetic & Spatial Components

- **ParticleText / TextType / TrueFocus:** Reserved for ceremonial surfaces such as the daily gate. They are not used on the dashboard, whose first viewport belongs to the current goal.
- **Lightfall / SideRays:** Shader atmosphere with CSS or static fallbacks when WebGL is unavailable.
- **GlassIcons / GlassJumper:** Spatial shortcuts with real accessible buttons layered over visual icons. Not used on the dashboard, where they duplicated PillNav; available for surfaces that have no other navigation.
- **Cubes / InfiniteSpiral / Masonry / Folder:** Activity, recency, mail, and programs through distinct spatial metaphors.
- **EvilEye:** Reserved for Halt, where vigilant attention is semantically appropriate.
- **ClickSpark / GlowCursor:** Fine-pointer feedback only; disable under reduced motion and never obscure focus or input.

### Live-Signal Panel

The floating signal plate is signature: translucent glass, slight rotation, amber metadata, prominent value, and concise copy. It becomes an aligned full-width block on mobile.

### Surfaces

Today's execution and operational maintenance are separate pages. `/` holds Now, the day's metrics, activity evidence, and the plan editor. `/ops` holds calendar, programs, mail, rituals, approvals, and sensor health. The dashboard links to it rather than stacking it below. PillNav is the one navigation system on both, naming only destinations that surface has, and its active item follows the section in view.

There is no dashboard search. What shipped before was a panel filter that scraped rendered text and hid whole cards; it neither searched the content people would look for nor explained an empty result, so it was removed rather than left to imply a capability that did not exist.

### Now Panel

The dashboard's first element and the only one guaranteed above the fold. It states the current goal, offers its status controls (start, done, partly done, defer, drop), and then the current time block with minutes remaining, the next event, and when activity evidence last arrived. Every goal for the day follows as a compact list with the same controls. It uses ordinary cards and native controls: this surface is read many times a day and answers "what now?", so it stays quiet.

### Goal States

Goals are stored entities with a lifecycle, not lines of text. `planned`, `active`, `done`, `partial`, `deferred`, and `dropped` each have a chip, a tone, and a one-line definition surfaced in the interface rather than left to be inferred. `partial` means real progress that is still actionable today, counts as half a goal, and carries forward. `deferred` means deliberately not worked on: it carries forward but is never offered as the next goal, because pushing something away should not hand it straight back. `dropped` leaves the count entirely rather than reading as a failure. At most one goal per day is `active`. Each goal shows one primary action — the ordinary next step for its state — with the exceptional outcomes behind a labelled menu, so deferring and dropping never compete visually with finishing. Deferring, partly finishing, or dropping a goal invites a one-line reason, and a goal pulled into a later day carries its lineage so repeated slippage is visible as "Carried over N times". Explicit status is the record of the day; nothing infers it.

### Recap

The recap is a decision loop, not a slideshow, and it closes on "Close the day" rather than "I saw this." Seven steps, three of them interactive: judge every goal (with a reason for partial, deferred, and dropped), correct anything the classifier read wrong, and keep one lesson. Interactive steps read live goal and evidence state rather than the snapshot stored with the cards, so a status changed mid-recap is never stale. The closing step names exactly what carries into tomorrow, with each goal's reason and slip count attached.

The day cannot close while a goal is still unjudged, and the rule lives in the store rather than the button. `ack_recap` refuses a day holding `planned` or `active` goals and names them; the API returns 400. A disabled button is a courtesy to one client, while the day's record has to be unambiguous for every client — the legacy overlay, a second tab, a stale browser. The interface gates the same rule ahead of time so the refusal is rare, and reloads the goals if it ever fires.

"Close the day" is disabled and the block appears above the controls, not beneath them, offering the two ways forward: jump back to judge them individually, or defer the rest with one reason. Deferring in bulk is itself a judgement, which is the point — an unanswered record is the one outcome the recap will not accept. Every settled status counts as judged, including dropped; a day with no plan closes freely.

Week comparison plots goals set against goals finished. It never compares planned blocks with logged events: those are unlike units and the ratio meant nothing.

### Plan Safety

A plan the system cannot honour is refused, not saved: a block ending before it starts, or two blocks claiming the same minutes, is an inline error that disables the save button and marks the offending field. Everything else is a warning that informs the commitment without blocking it — an overloaded day, a block running hours without a break, a collision with something already on the calendar, more goals than a day holds. The rules live in `plan-validation.js` and `planning.py` and are enforced in both, so the legacy overlay pages cannot write a schedule the dashboard would reject.

The editor states its total planned hours, tracks Saved / Unsaved changes / Saving, keeps a per-day draft through a reload, and asks before switching dates with unsaved work.

### Goal Removal

Archived goals are recoverable through the product, not only the API: the plan editor lists what was removed from that day with its status and notes, and restores it in place. The immediate Undo covers the accident; this covers the change of mind a week later.

Removing a goal that has any history — a status beyond planned, a note, a completion, or carried lineage — archives it rather than deleting it, and the editor says so alongside an Undo. A goal that was never acted on is simply deleted; it was a typo, not a record. Archived goals leave the day's counts and can be restored with their status and notes intact. Removing a goal detaches any time blocks pointing at it, and the undo strip names how many.

### Execution

Time blocks carry stable ids and can be started, paused, and finished, accumulating tracked time. Only one block runs at a time per day. Observed minutes falling inside a block are attributed to that block's goal and reported separately from the alignment buckets, because scheduling proximity is weak evidence and must not be dressed as proof.

A block's id is its execution history. Every client must echo it back on save; a client that does not gets it inherited from the stored block it exactly matches, and a fresh id only when that match is ambiguous. Losing the id silently orphans recorded work, which reads to the owner as the product forgetting what they did.

### One Active Work Context

Goal, running block, and focus session are stored separately and can drift apart, so they are reconciled into a single answer to "what am I doing now." Starting work sets all three in one move: the goal becomes active, its block for the current window starts, and any focus session is bound to that goal. Stopping work pauses the block and ends focus without judging anything, because putting the day down is not the same as finishing it.

Switching work is one database transaction, not merely one call: the store's commits route through a guard, and `start_work` runs on a savepoint that rolls back whole. Only a clean finish earns a commit — if the savepoint cannot be opened, the undo fails, or the release fails, the whole transaction is discarded rather than written, because committing after a failed undo is exactly how half a change reaches the file.

When the database cannot be unwound at all, uncommitted is not the same as discarded: the abandoned writes sit in an open transaction that the next ordinary write would publish, minutes later and from unrelated code. So a store whose rollback fails is poisoned. Its connection is closed, which throws the open transaction away, and every later call raises `StoreUnavailable` until `reconnect()` is called deliberately. A failed commit propagates for the same reason — reporting success for work that is not on disk is worse than the failure. The API answers 503 and the dashboard says a restart is needed and no work was lost.

The suite pins `TIMELESS_TZ` rather than inheriting it. Several tests assert this app's date arithmetic by name — which day a late-evening UTC event belongs to, when the recap window opens — so an inherited zone would make them pass on one machine and fail on another.

Tests that reason about "now" freeze the clock rather than offsetting the real one. `active_work` reads the wall clock to decide which block covers the current minute, so its tests build windows hours either side; anchored to the real time of day, a two-hour offset wraps past midnight after about 21:00, turning an upcoming block into `23:30 → 00:30` that sorts before everything else. The suite then passes all afternoon and fails in the evening. The fixture pins local noon, and the window helper asserts it never crosses midnight.

Note that releasing the outermost savepoint is what actually commits under this driver; the explicit `commit()` afterwards is belt and braces. The unwind logic is written for that, and a test documents it so the behaviour is not rediscovered by accident. The goal becomes active, its block starts, and any live focus session is re-bound to the new goal carrying its remaining time and level — or, if any step fails, none of it happens. A goal cannot end up switched with its focus left behind. A session is never left attached to the goal you switched away from — detecting that afterwards would be a contradiction the switch itself created.

Now derives its headline goal and its next action from that single reconciled result and never recomputes either. The next action always describes the headline goal, falling back through running block, scheduled block, upcoming block, and finally the goal itself.

What remains are real divergences between intent and schedule, not internal disagreement: a block running past its window, work running during another block's slot, a block scheduled now for a different goal, focus protecting something else. Each is named in plain words at the top of Now and carries the action that resolves it — `finish_block` or `switch_work` — so the interface dispatches on the server's decision rather than inferring one. The owner is never left to reconcile system state in their head.

### Goal-Only Days

A plan needs a goal. It does not need a schedule. Requiring a time block only taught people to type a placeholder one to get past the gate, which is worse than an honest empty timeline. The missing-goal case is caught inline before submission rather than by the server afterwards.

### Visual Effects Budget

This is load shedding, not thermal measurement, and the distinction matters. The browser exposes no temperature, power draw, or thermal-pressure signal, so nothing here can prove a laptop is hot — a GPU can hold 60fps while drawing serious power. What the budget does is stop the expensive layer whenever the cheap proxies say it is probably not worth paying for: reduced motion, running on battery, data saver, or visibly dropping frames. Confirming a fan problem still needs a real energy trace on the machine.

Frame timing is sampled in short bursts rather than continuously, so the probe for cost is not itself a cost. The first sample runs a few seconds after load rather than half a minute in, and a reading latches, because a threshold that flips back and forth would restart the shader repeatedly. The Battery API exists only in Chromium; where it is missing nothing is assumed, and the sampler and the manual switch carry the weight.

Reduced motion is evaluated before the manual switch. It is an accessibility preference, not a performance hint, so choosing "Full" cannot override it, and the control says so when that happens. Otherwise a three-way Auto / Full / Quiet control in the Theme popover overrides the automatic decision in either direction and states in plain words why effects are currently down. The full-viewport shader, click sparks, side rays, and the recency spiral all yield to it.

### Notes and Dialogs

Reasons for an outcome are captured in a real dialog, never `window.prompt`. The prompt could not say whether a reason was optional, gave no confirmation, ignored the page's visual language, and behaves inconsistently on mobile and with assistive technology. The replacement is a labelled modal with focus moved in on open, trapped while open, and returned to whatever opened it, Escape to cancel, and Cmd/Ctrl+Enter to confirm. Focus is restored from the dialog instance's own cleanup: the dialog is mounted only while open, so that is the code that actually runs when it closes. Behaviour like this is covered by DOM tests rather than by reading the source for a `focus()` call, which proves only that one was written.

### Keyboard and Screen Reader

A component that declares `role="menu"` keeps the promise: Arrow keys move between items, Home and End jump to the ends, Arrow Up or Down opens the menu with the matching end focused, Tab leaves and closes, Escape closes and returns focus to the trigger. Menu items are reached by roving focus rather than becoming extra tab stops.

Invalid time fields carry `aria-describedby` pointing at the message that explains them, so the reason is heard and not only the fact of the error. Plan-level errors announce as an alert. Toasts live in a polite live region.

### Estimated Measures

Any number derived from observed activity is labelled as an estimate and never shown alone, and every estimate is correctable: a ruling from the owner replaces the classifier's guess for that day and the estimate is rebuilt from it. Observed items are shown by a readable label, never a raw window title or reverse-DNS bundle id. The alignment figure always travels with its basis — minutes observed, minutes judged, minutes unclassified — plus a confidence chip and a plain statement of the method. Charts plot only measured dimensions; an unmeasured one is labelled "Not measured" and excluded from the shape, never plotted as zero.

## Do's and Don'ts

- **Do** use the supplied React Bits components in their intended semantic regions, behind the first useful action rather than in front of it.
- **Do** preserve the tension between warm physical ground and dark dimensional command space.
- **Do** make motion expressive while keeping state, hierarchy, and actions immediately readable.
- **Do** honor `prefers-reduced-motion`, keyboard focus, semantic text, and static fallbacks for canvas, OGL, and WebGL.
- **Do** retain dense bento, spatial glass, desktop pill navigation, and the mobile dynamic menu.
- **Don't** regress to the previous quiet, native-only, low-motion dashboard direction.
- **Don't** turn glass into low-contrast fog; retain bright edges, readable text, and depth separation.
- **Don't** animate routine prose or every card. Concentrate kinetics at focal transitions and live signals.
- **Don't** let shader effects, cursor trails, particles, or overlays capture input, hide focus, or block workflows.
- **Don't** use flat generic tiles where a supplied spatial component carries the information more distinctly.
- **Don't** put branding, typed status, or a second set of shortcuts ahead of the current goal in the first viewport.
- **Don't** present an estimate as a verdict: no bare percentage without its coverage, confidence, and method, and no absent measurement drawn as a zero.
