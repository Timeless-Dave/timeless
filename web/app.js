async function api(path, opts) {
  const token = new URLSearchParams(location.search).get("token") || localStorage.getItem("timeless_token") || "";
  if (new URLSearchParams(location.search).get("token")) {
    localStorage.setItem("timeless_token", new URLSearchParams(location.search).get("token"));
  }
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  const sep = path.includes("?") ? "&" : "?";
  const url = token && !path.startsWith("http") ? path + sep + "token=" + encodeURIComponent(token) : path;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  let r;
  try {
    r = await fetch(url, { headers, signal: controller.signal, ...opts });
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The request timed out");
    throw new Error("Could not connect to Timeless");
  } finally {
    clearTimeout(timeout);
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || r.statusText);
  return data;
}

function el(id) {
  return document.getElementById(id);
}
