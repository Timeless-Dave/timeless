(function () {
  const DEFAULT = [208, 135, 38];
  const root = document.documentElement;

  function hex(r, g, b) {
    return "#" + [r, g, b].map((n) => Number(n).toString(16).padStart(2, "0")).join("");
  }

  function load() {
    const raw = (localStorage.getItem("timeless_rgb") || "").split(",").map((n) => parseInt(n, 10));
    const rgb = raw.length === 3 && raw.every((n) => n >= 0 && n <= 255) ? raw : DEFAULT.slice();
    apply(rgb[0], rgb[1], rgb[2]);
    return { rgb };
  }

  function apply(r, g, b) {
    root.style.setProperty("--accent", hex(r, g, b));
    root.style.setProperty("--accent-rgb", `${r}, ${g}, ${b}`);
  }

  function bind() {
    const box = document.getElementById("theme-box");
    if (!box) return;
    const state = load();
    const rs = ["theme-r", "theme-g", "theme-b"].map((id) => document.getElementById(id));
    const hexEl = document.getElementById("theme-hex");
    rs.forEach((el, i) => { if (el) el.value = String(state.rgb[i]); });
    const sync = () => {
      const rgb = rs.map((el) => parseInt(el.value, 10) || 0);
      localStorage.setItem("timeless_rgb", rgb.join(","));
      apply(rgb[0], rgb[1], rgb[2]);
      if (hexEl) hexEl.textContent = hex(rgb[0], rgb[1], rgb[2]);
    };
    sync();
    rs.forEach((el) => el && el.addEventListener("input", sync));
    document.getElementById("theme-reset")?.addEventListener("click", () => {
      localStorage.removeItem("timeless_rgb");
      rs.forEach((el, i) => { if (el) el.value = String(DEFAULT[i]); });
      sync();
    });
  }

  load();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
})();
