import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RadioGroup from '@/components/RadioGroup';

const OPTIONS = [
  ['auto', 'Auto'],
  ['full', 'Full'],
  ['quiet', 'Quiet'],
];

function Host({ value = 'auto', onChange = () => {} }) {
  return (
    <>
      <p id="effects-label">Visual effects</p>
      <RadioGroup labelId="effects-label" options={OPTIONS} value={value} onChange={onChange} />
    </>
  );
}

const radios = () => screen.getAllByRole('radio');

describe('RadioGroup', () => {
  it('marks the current value as checked with a single tab stop', () => {
    render(<Host value="full" />);
    expect(screen.getByRole('radio', { name: 'Full' }).getAttribute('aria-checked')).toBe('true');
    expect(screen.getByRole('radio', { name: 'Auto' }).getAttribute('tabindex')).toBe('-1');
    expect(screen.getByRole('radio', { name: 'Full' }).getAttribute('tabindex')).toBe('0');
  });

  it('moves focus with arrow keys without changing the value', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Host value="auto" onChange={onChange} />);
    screen.getByRole('radio', { name: 'Auto' }).focus();
    await user.keyboard('{ArrowRight}');
    expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'Full' }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it('selects with Space and Enter', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Host value="auto" onChange={onChange} />);
    await user.click(screen.getByRole('radio', { name: 'Auto' }));
    await user.keyboard('{ArrowRight}{Enter}');
    expect(onChange).toHaveBeenCalledWith('full');
    onChange.mockClear();
    await user.keyboard('{ArrowLeft}{ }');
    expect(onChange).toHaveBeenCalledWith('auto');
  });

  it('jumps to the ends with Home and End', async () => {
    const user = userEvent.setup();
    render(<Host value="auto" />);
    await user.click(screen.getByRole('radio', { name: 'Auto' }));
    await user.keyboard('{End}');
    expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'Quiet' }));
    await user.keyboard('{Home}');
    expect(document.activeElement).toBe(screen.getByRole('radio', { name: 'Auto' }));
  });
});
