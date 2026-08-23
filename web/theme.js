(function () {
  const DEFAULT = [157, 92, 255];
  const root = document.documentElement;

  function hex(r, g, b) {
    return "#" + [r, g, b].map((n) => Number(n).toString(16).padStart(2, "0")).join("");
  }

  function load() {
    const raw = (localStorage.getItem("timeless_rgb") || "").split(",").map((n) => parseInt(n, 10));
    const rgb = raw.length === 3 && raw.every((n) => n >= 0 && n <= 255) ? raw : DEFAULT.slice();
    const tint = localStorage.getItem("timeless_tint") === "full" ? "full" : "accent";
    apply(rgb[0], rgb[1], rgb[2], tint);
    return { rgb, tint };
  }

  function apply(r, g, b, tint) {
    root.style.setProperty("--accent", hex(r, g, b));
    root.style.setProperty("--accent-rgb", `${r}, ${g}, ${b}`);
    if (tint === "full") {
      root.style.setProperty("--bg", `rgb(${Math.round(r * 0.06)}, ${Math.round(g * 0.06)}, ${Math.round(b * 0.06)})`);
      root.style.setProperty("--card", `rgb(${Math.round(r * 0.14)}, ${Math.round(g * 0.14)}, ${Math.round(b * 0.14)})`);
      root.style.setProperty("--line", `rgb(${Math.round(r * 0.28)}, ${Math.round(g * 0.28)}, ${Math.round(b * 0.28)})`);
      root.style.setProperty("--muted", `rgb(${Math.round(120 + r * 0.25)}, ${Math.round(110 + g * 0.25)}, ${Math.round(90 + b * 0.2)})`);
    } else {
      root.style.removeProperty("--bg");
      root.style.removeProperty("--card");
      root.style.removeProperty("--line");
      root.style.removeProperty("--muted");
    }
  }

  function bind() {
    const box = document.getElementById("theme-box");
    if (!box) return;
    const state = load();
    const rs = ["theme-r", "theme-g", "theme-b"].map((id) => document.getElementById(id));
    const hexEl = document.getElementById("theme-hex");
    const tintEl = document.getElementById("theme-tint");
    rs.forEach((el, i) => { if (el) el.value = String(state.rgb[i]); });
    if (tintEl) tintEl.checked = state.tint === "full";
    const sync = () => {
      const rgb = rs.map((el) => parseInt(el.value, 10) || 0);
      const tint = tintEl && tintEl.checked ? "full" : "accent";
      localStorage.setItem("timeless_rgb", rgb.join(","));
      localStorage.setItem("timeless_tint", tint);
      apply(rgb[0], rgb[1], rgb[2], tint);
      if (hexEl) hexEl.textContent = hex(rgb[0], rgb[1], rgb[2]);
    };
    sync();
    rs.forEach((el) => el && el.addEventListener("input", sync));
    if (tintEl) tintEl.addEventListener("change", sync);
    document.getElementById("theme-reset")?.addEventListener("click", () => {
      localStorage.removeItem("timeless_rgb");
      localStorage.removeItem("timeless_tint");
      rs.forEach((el, i) => { if (el) el.value = String(DEFAULT[i]); });
      if (tintEl) tintEl.checked = false;
      sync();
    });
    document.getElementById("theme-toggle")?.addEventListener("click", () => {
      box.classList.toggle("open");
    });
  }

  load();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
