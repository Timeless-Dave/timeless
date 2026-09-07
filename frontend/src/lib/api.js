export async function api(path, opts = {}) {
  const token =
    new URLSearchParams(location.search).get('token') ||
    localStorage.getItem('timeless_token') ||
    '';
  if (new URLSearchParams(location.search).get('token')) {
    localStorage.setItem('timeless_token', new URLSearchParams(location.search).get('token'));
  }
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers.Authorization = 'Bearer ' + token;
  const sep = path.includes('?') ? '&' : '?';
  const url =
    token && !path.startsWith('http') ? path + sep + 'token=' + encodeURIComponent(token) : path;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  let response;
  try {
    response = await fetch(url, { ...opts, headers, signal: controller.signal });
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The request timed out');
    throw new Error('Could not connect to Timeless');
  } finally {
    clearTimeout(timeout);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || response.statusText);
    error.status = response.status;
    // The service is up but its database connection was discarded mid-transaction.
    // Nothing was lost; it needs a restart, and saying so beats a bare error.
    if (response.status === 503) {
      error.message = `${error.message}. Restart Timeless to continue; no work was lost.`;
    }
    throw error;
  }
  return data;
}
