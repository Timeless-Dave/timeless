# Product

## Platform

web

## Users

Timeless is a private, single-user system for its owner. It is used throughout the day from a MacBook and a Samsung phone, including away from the home network.

## Product Purpose

Timeless helps its owner follow through on the day they intended to have. It combines daily goals, scheduled classes and meetings, productivity evidence, applications and conferences, email signals, reminders, and calendar context in one operational view.

Success means the owner can quickly see what matters now, act on it, and later understand whether time was spent on planned work, productive off-plan work, distraction, or activity that could not be classified.

## Positioning

Timeless compares stated intentions with observed activity while keeping the underlying evidence inspectable. It coordinates local device signals and selected cloud services without turning raw browsing or private activity into an indiscriminate history feed.

## Operating Context

- The MacBook runs the Timeless service and local activity integrations.
- The Samsung phone accesses the dashboard remotely through Tailscale.
- Google Sheets tracks internships, conferences, hackathons, and related programs.
- Calendar and email provide time-sensitive commitments and reminders.
- Academic courses and dates change by semester and remain semester-scoped.
- The dashboard is an operational tool used repeatedly, often in short sessions.

## Capabilities and Constraints

- Preserve the existing routes, workflows, stored data, and integration behavior.
- Remain local-first, private, and approximately zero-cost.
- Support responsive desktop and mobile web use.
- The dashboard ships as a Vite + React SPA in `frontend/`, built to `frontend/dist` and served by FastAPI with legacy `web/` as fallback until the first build exists.
- Overlay routes (`/gate`, `/halt`, `/recap`) stay available to the Mac overlay and phone.
- GPU-backed React Bits backgrounds (GSAP, WebGL) are allowed on the dashboard when they respect `prefers-reduced-motion: reduce` and the mobile single-layer WebGL cap.
- Avoid unnecessary runtime dependencies beyond the SPA toolchain, public port forwarding, and collection of complete browser history.
- Remote dashboard access uses Tailscale. Android wireless ADB remains limited by Android network constraints until replaced by a native phone uploader.

## Brand Commitments

- Name: Timeless.
- Voice: direct, calm, concise, and practical.
- The interface should feel clean and intentional. Hero motion and shader backgrounds are experimental accents, not the default for every surface.
- Simplicity is the governing standard. Motion and visual effects must communicate hierarchy, feedback, or state, and must pause or simplify under reduced motion.

## Evidence on Hand

- Working dashboard SPA under `frontend/` and legacy overlay surfaces under `web/`.
- Existing local integrations and API behavior under `src/timeless/`.
- A semester course configuration and imported academic calendar workflow.
- Real productivity, meeting, program, mail, and sensor data supplied by the local service.

## Product Principles

1. Show the next useful action before secondary analysis.
2. Preserve privacy by collecting only the evidence needed for an explicit feature.
3. Distinguish planned progress, productive detours, distraction, and unknown activity honestly.
4. Keep every important workflow usable from both the MacBook and phone.
5. Prefer a small number of dependable mechanisms over decorative features or redundant controls.

## Accessibility & Inclusion

Keyboard navigation, visible focus, readable contrast, reduced-motion support, touch-sized controls, and layouts without accidental horizontal scrolling are required.
