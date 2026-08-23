(function (root) {
  let openEl = null;
  let onDocClick = null;
  let onKey = null;

  function closePop() {
    if (!openEl) return;
    openEl.classList.remove("open");
    openEl = null;
    if (onDocClick) {
      document.removeEventListener("click", onDocClick, true);
      onDocClick = null;
    }
    if (onKey) {
      document.removeEventListener("keydown", onKey);
      onKey = null;
    }
  }

  function openPop(el) {
    if (!el) return;
    if (openEl && openEl !== el) closePop();
    openEl = el;
    el.classList.add("open");
    onDocClick = (e) => {
      if (el.contains(e.target)) return;
      const toggle = document.querySelector(`[data-pop-toggle="${el.id}"]`);
      if (toggle && toggle.contains(e.target)) return;
      closePop();
    };
    onKey = (e) => {
      if (e.key === "Escape") closePop();
    };
    setTimeout(() => {
      document.addEventListener("click", onDocClick, true);
      document.addEventListener("keydown", onKey);
    }, 0);
  }

  function bindPopToggles() {
    document.querySelectorAll("[data-pop-toggle]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = btn.getAttribute("data-pop-toggle");
        const panel = id ? document.getElementById(id) : btn.nextElementSibling;
        if (!panel) return;
        if (openEl === panel) closePop();
        else openPop(panel);
      });
    });
  }

  let toastTimer = null;
  function toast(msg, tone) {
    let box = document.getElementById("ui-toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "ui-toast";
      box.className = "toast";
      document.body.appendChild(box);
    }
    box.textContent = msg;
    box.className = "toast show" + (tone ? " toast-" + tone : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => box.classList.remove("show"), 3200);
  }

  function sparkline(values, color, w, h) {
    const data = values.length ? values : [0];
    const max = Math.max(...data, 1);
    const min = Math.min(...data, 0);
    const span = max - min || 1;
    const pts = data.map((v, i) => {
      const x = (i / Math.max(data.length - 1, 1)) * w;
      const y = h - ((v - min) / span) * (h - 4) - 2;
      return [x, y];
    });
    const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    const area = line + " L" + w + " " + h + " L0 " + h + " Z";
    const gid = "sg" + Math.random().toString(36).slice(2, 8);
    return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">
      <defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${color}" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
      </linearGradient></defs>
      <path d="${area}" fill="url(#${gid})"/>
      <path d="${line}" fill="none" stroke="${color}" stroke-width="1.5"/>
    </svg>`;
  }

  function barChart(days, w, h) {
    const data = days.length ? days : [{ label: "—", count: 0 }];
    const max = Math.max(...data.map((d) => d.count || 0), 1);
    const pad = { l: 28, r: 8, t: 8, b: 22 };
    const innerW = w - pad.l - pad.r;
    const innerH = h - pad.t - pad.b;
    const gap = 4;
    const barW = Math.max(4, (innerW - gap * (data.length - 1)) / data.length);
    const bars = data.map((d, i) => {
      const bh = Math.max(2, ((d.count || 0) / max) * innerH);
      const x = pad.l + i * (barW + gap);
      const y = pad.t + innerH - bh;
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${bh.toFixed(1)}" rx="5" fill="var(--accent)"/>`;
    }).join("");
    const labels = data.map((d, i) => {
      const x = pad.l + i * (barW + gap) + barW / 2;
      const lbl = (d.label || "").slice(5) || d.label || "";
      return `<text x="${x.toFixed(1)}" y="${h - 4}" text-anchor="middle" class="chart-axis">${lbl}</text>`;
    }).join("");
    const grid = [0.25, 0.5, 0.75, 1].map((f) => {
      const y = pad.t + innerH * (1 - f);
      return `<line x1="${pad.l}" y1="${y}" x2="${w - pad.r}" y2="${y}" class="chart-grid"/>`;
    }).join("");
    return `<svg class="chart-bars" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">${grid}${bars}${labels}</svg>`;
  }

  function rangeBar(pct) {
    const p = Math.max(0, Math.min(100, pct));
    const marker = 8 + (p / 100) * 84;
    return `<div class="range-bar" role="img" aria-label="Progress ${p}%">
      <div class="range-track"></div>
      <div class="range-marker" style="left:${marker}%"></div>
      <div class="range-labels"><span>0</span><span>50</span><span>100</span></div>
    </div>`;
  }

  function rulerTicks(active) {
    return Array.from({ length: 9 }, (_, i) => {
      const on = i === active;
      return `<span class="tick${on ? " on" : ""}"></span>`;
    }).join("");
  }

  function trendArrow(dir) {
    const up = dir === "up";
    const color = up ? "var(--alert)" : "var(--ok-icon)";
    return `<svg class="trend" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">
      <path d="${up ? "M12 4l6 8h-4v8h-4v-8H6z" : "M12 20l6-8h-4V4h-4v8H6z"}" fill="${color}"/>
    </svg>`;
  }

  function iconPlan() {
    return `<svg viewBox="0 0 24 24" fill="none"><rect x="4" y="5" width="16" height="15" rx="2" stroke="currentColor" stroke-width="1.8"/><path d="M8 9h8M8 13h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
  }
  function iconEvents() {
    return `<svg viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="16" rx="2" stroke="currentColor" stroke-width="1.8"/><path d="M8 3v4M16 3v4M3 10h18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;
  }
  function iconApprovals() {
    return `<svg viewBox="0 0 24 24" fill="none"><path d="M9 11l2 2 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><rect x="4" y="4" width="16" height="16" rx="3" stroke="currentColor" stroke-width="1.8"/></svg>`;
  }

  root.UI = {
    openPop,
    closePop,
    bindPopToggles,
    toast,
    sparkline,
    barChart,
    rangeBar,
    rulerTicks,
    trendArrow,
    iconPlan,
    iconEvents,
    iconApprovals,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindPopToggles);
  } else {
    bindPopToggles();
  }
})(typeof window !== "undefined" ? window : globalThis);
