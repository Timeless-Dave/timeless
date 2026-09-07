import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MenuButton from '@/components/MenuButton';

function Host({ onPick = () => {} }) {
  return (
    <>
      <button type="button">Before</button>
      <MenuButton label="More">
        {['Partly done', 'Defer', 'Drop'].map(label => (
          <button key={label} type="button" role="menuitem" tabIndex={-1} className="menu-item" onClick={() => onPick(label)}>
            {label}
          </button>
        ))}
      </MenuButton>
      <button type="button">After</button>
    </>
  );
}

const items = () => screen.getAllByRole('menuitem');

describe('MenuButton', () => {
  it('reports its expanded state', async () => {
    const user = userEvent.setup();
    render(<Host />);
    const trigger = screen.getByRole('button', { name: 'More' });
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(trigger.getAttribute('aria-haspopup')).toBe('menu');
    await user.click(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
  });

  it('focuses the first item on open and the last when opened with Arrow Up', async () => {
    const user = userEvent.setup();
    render(<Host />);
    const trigger = screen.getByRole('button', { name: 'More' });
    await user.click(trigger);
    await waitFor(() => expect(document.activeElement).toBe(items()[0]));

    await user.keyboard('{Escape}');
    trigger.focus();
    await user.keyboard('{ArrowUp}');
    await waitFor(() => expect(document.activeElement).toBe(items()[2]));
  });

  it('moves through items with the arrow keys and wraps', async () => {
    const user = userEvent.setup();
    render(<Host />);
    await user.click(screen.getByRole('button', { name: 'More' }));
    await waitFor(() => expect(document.activeElement).toBe(items()[0]));

    await user.keyboard('{ArrowDown}');
    expect(document.activeElement).toBe(items()[1]);
    await user.keyboard('{ArrowDown}{ArrowDown}');
    expect(document.activeElement).toBe(items()[0]);
    await user.keyboard('{ArrowUp}');
    expect(document.activeElement).toBe(items()[2]);
  });

  it('jumps to the ends with Home and End', async () => {
    const user = userEvent.setup();
    render(<Host />);
    await user.click(screen.getByRole('button', { name: 'More' }));
    await waitFor(() => expect(document.activeElement).toBe(items()[0]));
    await user.keyboard('{End}');
    expect(document.activeElement).toBe(items()[2]);
    await user.keyboard('{Home}');
    expect(document.activeElement).toBe(items()[0]);
  });

  it('closes on Escape and returns focus to the trigger', async () => {
    const user = userEvent.setup();
    render(<Host />);
    const trigger = screen.getByRole('button', { name: 'More' });
    await user.click(trigger);
    await waitFor(() => expect(document.activeElement).toBe(items()[0]));
    await user.keyboard('{Escape}');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(trigger);
  });

  it('runs the chosen item and closes', async () => {
    const onPick = vi.fn();
    const user = userEvent.setup();
    render(<Host onPick={onPick} />);
    await user.click(screen.getByRole('button', { name: 'More' }));
    await user.click(screen.getByRole('menuitem', { name: 'Defer' }));
    expect(onPick).toHaveBeenCalledWith('Defer');
    expect(screen.getByRole('button', { name: 'More' }).getAttribute('aria-expanded')).toBe('false');
  });

  it('does not add its items to the tab sequence', async () => {
    const user = userEvent.setup();
    render(<Host />);
    // Tab order steps over the closed menu's items entirely.
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Before' }));
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'More' }));
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'After' }));
  });
});
