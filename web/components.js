(function () {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function initPillNavigation() {
    const buttons = [...document.querySelectorAll(".rail-btn[data-scroll]")];
    const targets = buttons.map((button) => document.getElementById(button.dataset.scroll)).filter(Boolean);
    if (!("IntersectionObserver" in window) || !targets.length) return;
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      buttons.forEach((button) => button.classList.toggle("on", button.dataset.scroll === visible.target.id));
    }, { root: document.querySelector(".page-body"), rootMargin: "-18% 0px -62%", threshold: [0.05, 0.35] });
    targets.forEach((target) => observer.observe(target));
  }

  function initGoalFocus() {
    document.addEventListener("click", (event) => {
      const chip = event.target.closest("[data-plan-preset]");
      if (!chip) return;
      chip.setAttribute("aria-pressed", "true");
      chip.classList.add("is-selected");
    });
  }

  function initClickFeedback() {
    if (reduceMotion.matches) return;
    const canvas = document.createElement("canvas");
    canvas.className = "click-feedback";
    canvas.setAttribute("aria-hidden", "true");
    document.body.appendChild(canvas);
    const context = canvas.getContext("2d");
    const sparks = [];
    let frame = 0;

    function resize() {
      const scale = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(innerWidth * scale);
      canvas.height = Math.round(innerHeight * scale);
      canvas.style.width = innerWidth + "px";
      canvas.style.height = innerHeight + "px";
      context.setTransform(scale, 0, 0, scale, 0, 0);
    }

    function draw(now) {
      context.clearRect(0, 0, innerWidth, innerHeight);
      for (let index = sparks.length - 1; index >= 0; index -= 1) {
        const spark = sparks[index];
        const progress = Math.min(1, (now - spark.started) / 320);
        if (progress >= 1) { sparks.splice(index, 1); continue; }
        const distance = 7 + 14 * (1 - Math.pow(1 - progress, 3));
        const length = 6 * (1 - progress);
        context.globalAlpha = 1 - progress;
        context.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#b86f20";
        context.lineWidth = 1.5;
        context.beginPath();
        context.moveTo(spark.x + Math.cos(spark.angle) * distance, spark.y + Math.sin(spark.angle) * distance);
        context.lineTo(spark.x + Math.cos(spark.angle) * (distance + length), spark.y + Math.sin(spark.angle) * (distance + length));
        context.stroke();
      }
      context.globalAlpha = 1;
      frame = sparks.length ? requestAnimationFrame(draw) : 0;
    }

    document.addEventListener("click", (event) => {
      if (!event.target.closest("button, a, [role='button']")) return;
      for (let index = 0; index < 6; index += 1) {
        sparks.push({ x: event.clientX, y: event.clientY, angle: Math.PI * 2 * index / 6, started: performance.now() });
      }
      if (!frame) frame = requestAnimationFrame(draw);
    }, { passive: true });
    addEventListener("resize", resize, { passive: true });
    resize();
  }

  function init() {
    initPillNavigation();
    initGoalFocus();
    initClickFeedback();
    requestAnimationFrame(() => document.documentElement.classList.add("ui-ready"));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
