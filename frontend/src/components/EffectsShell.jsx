import ClickSpark from '@/components/ClickSpark';
import { useGpuBudget } from '@/hooks/useGpuBudget';

export default function EffectsShell({ children, sparkColor }) {
  const { quiet } = useGpuBudget();

  const inner = <div className="effects-shell__content">{children}</div>;

  if (quiet) return inner;

  const color = sparkColor || 'var(--accent)';

  return (
    <ClickSpark sparkColor={color} sparkCount={7} sparkSize={12} sparkRadius={22} duration={380} extraScale={1.1}>
      {inner}
    </ClickSpark>
  );
}
