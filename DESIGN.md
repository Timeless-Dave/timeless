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

This is deliberately high-variance and high-motion (variance 9, motion 9, density 7). React Bits components are authored language, not optional decoration: ParticleText, Lightfall, SideRays, GlassIcons, TrueFocus, TextType, Cubes, InfiniteSpiral, Masonry, Folder, EvilEye, ClickSpark, GlowCursor, and BentoAnalytics each retain a meaningful role. Motion, canvas, OGL, and shaders always yield to reduced-motion settings, missing WebGL, constrained devices, and semantic fallbacks.

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

The app occupies a bounded 1440px shell on warm ground. Its core is intentionally asymmetric: the operational stream sits beside a narrower dark sensor rail, while the overview opens with a contained, non-shrinking dimensional stage (`flex: 0 0 auto`, minimum 850px) containing the glass hero, floating signal card, commands, and the complete GlassJumper shortcut layer inside its clipped boundary. Bento spans, masonry, folders, and spiral media create controlled density without equalizing every module.

Desktop navigation is a sticky 42px pill assembly with animated logo and circular hover reveals. At 768px it becomes a logo-and-hamburger system with a rounded dynamic menu; the signal card rejoins document flow and the stage becomes a tall, natural-flow field (minimum 1380px) so its hero, actions, commands, and GlassJumper shortcuts remain contained without clipping or compression. At 1100px multi-column command content stacks. Touch targets, safe-area clearance, readable flow, and freedom from horizontal overflow remain mandatory.

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

- **ParticleText / TextType / TrueFocus:** Identity, current action, and transitional emphasis. TextType types one short semantic status once, without cycling, then holds the completed phrase as stable state.
- **Lightfall / SideRays:** Shader atmosphere with CSS or static fallbacks when WebGL is unavailable.
- **GlassIcons / GlassJumper:** Spatial shortcuts with real accessible buttons layered over visual icons. The entire shortcut layer stays inside the command-stage boundary on desktop and in the mobile stage's natural flow.
- **Cubes / InfiniteSpiral / Masonry / Folder:** Activity, recency, mail, and programs through distinct spatial metaphors.
- **EvilEye:** Reserved for Halt, where vigilant attention is semantically appropriate.
- **ClickSpark / GlowCursor:** Fine-pointer feedback only; disable under reduced motion and never obscure focus or input.

### Live-Signal Panel

The floating signal plate is signature: translucent glass, slight rotation, amber metadata, prominent value, and concise copy. It becomes an aligned full-width block on mobile.

## Do's and Don'ts

- **Do** use every supplied React Bits component in its intended semantic region; the full-component directive defines this world.
- **Do** preserve the tension between warm physical ground and dark dimensional command space.
- **Do** make motion expressive while keeping state, hierarchy, and actions immediately readable.
- **Do** honor `prefers-reduced-motion`, keyboard focus, semantic text, and static fallbacks for canvas, OGL, and WebGL.
- **Do** retain dense bento, spatial glass, desktop pill navigation, and the mobile dynamic menu.
- **Don't** regress to the previous quiet, native-only, low-motion dashboard direction.
- **Don't** turn glass into low-contrast fog; retain bright edges, readable text, and depth separation.
- **Don't** animate routine prose or every card. Concentrate kinetics at focal transitions and live signals.
- **Don't** let shader effects, cursor trails, particles, or overlays capture input, hide focus, or block workflows.
- **Don't** use flat generic tiles where a supplied spatial component carries the information more distinctly.
