import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import NoteDialog from '@/components/NoteDialog';
import { useNotePrompt } from '@/hooks/useNotePrompt';

/** The real call-site shape: a trigger, and a dialog mounted only while open. */
function Host({ onResult }) {
  const { ask, dialogProps } = useNotePrompt();
  const [result, setResult] = useState('none');
  return (
    <>
      <button
        type="button"
        onClick={async () => {
          const value = await ask({ title: 'Defer: Read the paper', hint: 'Why it went this way.' });
          setResult(value === null ? 'cancelled' : value);
          onResult?.(value);
        }}
      >
        Defer
      </button>
      <span data-testid="result">{result}</span>
      {dialogProps.open ? <NoteDialog key={dialogProps.requestId} {...dialogProps} /> : null}
    </>
  );
}

describe('NoteDialog', () => {
  it('moves focus into the field when it opens', async () => {
    const user = userEvent.setup();
    render(<Host />);
    await user.click(screen.getByRole('button', { name: 'Defer' }));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
    expect(document.activeElement).toBe(screen.getByRole('textbox'));
  });

  it('returns focus to the trigger after saving', async () => {
    const user = userEvent.setup();
    render(<Host />);
    const trigger = screen.getByRole('button', { name: 'Defer' });
    await user.click(trigger);
    await user.type(screen.getByRole('textbox'), 'ran out of day');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(document.activeElement).toBe(trigger);
    expect(screen.getByTestId('result').textContent).toBe('ran out of day');
  });

  it('returns focus to the trigger after cancelling with Escape', async () => {
    const user = userEvent.setup();
    render(<Host />);
    const trigger = screen.getByRole('button', { name: 'Defer' });
    await user.click(trigger);
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(document.activeElement).toBe(trigger);
    expect(screen.getByTestId('result').textContent).toBe('cancelled');
  });

  it('traps Tab inside the dialog', async () => {
    const user = userEvent.setup();
    render(<Host />);
    await user.click(screen.getByRole('button', { name: 'Defer' }));
    const dialog = screen.getByRole('dialog');
    for (let i = 0; i < 6; i += 1) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });

  it('is announced as a modal with an accessible name and hint', async () => {
    const user = userEvent.setup();
    render(<Host />);
    await user.click(screen.getByRole('button', { name: 'Defer' }));
    const dialog = screen.getByRole('dialog');
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    expect(dialog).toHaveAccessibleName('Defer: Read the paper');
    expect(dialog).toHaveAccessibleDescription('Why it went this way.');
  });

  it('says the reason is optional', async () => {
    const user = userEvent.setup();
    render(<Host />);
    await user.click(screen.getByRole('button', { name: 'Defer' }));
    expect(screen.getByText('(optional)')).toBeTruthy();
  });

  it('starts each request from a clean field', async () => {
    const user = userEvent.setup();
    render(<Host />);
    const trigger = screen.getByRole('button', { name: 'Defer' });
    await user.click(trigger);
    await user.type(screen.getByRole('textbox'), 'first attempt');
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await user.click(trigger);
    expect(screen.getByRole('textbox').value).toBe('');
  });
});
