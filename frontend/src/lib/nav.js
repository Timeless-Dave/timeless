/** One navigation system. Each surface names only destinations it actually has,
 * and cross-page entries are routed rather than reloaded. */
export const TODAY_NAV = [
  { label: 'Now', href: '#now' },
  { label: 'Plan', href: '#panel-plan' },
  { label: 'Evidence', href: '#panel-evidence' },
  { label: 'Operations', href: '/ops' },
];

export const OPS_NAV = [
  { label: 'Today', href: '/' },
  { label: 'Events', href: '#panel-events' },
  { label: 'Programs', href: '#panel-programs' },
  { label: 'Mail', href: '#panel-mail' },
  { label: 'Approvals', href: '#panel-approvals' },
  { label: 'Signals', href: '#dark-sensors' },
];

export function scrollToHash(hash) {
  const id = hash.replace('#', '');
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Click handler for a PillNav slot: hashes scroll, routes navigate.
 * @param {(href: string) => void} navigate
 * @param {(href: string) => void} setActive
 */
export function navClickHandler(navigate, setActive) {
  return event => {
    const anchor = event.target.closest('a[href]');
    if (!anchor) return;
    const href = anchor.getAttribute('href');
    if (!href) return;
    event.preventDefault();
    if (href.startsWith('#')) {
      setActive(href);
      scrollToHash(href);
      return;
    }
    navigate(href);
  };
}
