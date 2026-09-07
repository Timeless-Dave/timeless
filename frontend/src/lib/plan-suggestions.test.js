import { describe, expect, it } from 'vitest';
import { courseTemplate, resolveTemplate, templatesForAcademics } from '@/lib/plan-suggestions';

describe('plan-suggestions', () => {
  it('maps standard presets to outcome and next-step pairs', () => {
    const template = resolveTemplate('LeetCode');
    expect(template.outcome).toMatch(/practice problem/i);
    expect(template.nextStep.length).toBeGreaterThan(10);
    expect(template.outcome).not.toBe('LeetCode');
  });

  it('builds course templates for unknown labels', () => {
    const template = courseTemplate('Calculus II');
    expect(template.outcome).toContain('Calculus II');
    expect(template.nextStep).toMatch(/concrete/i);
  });

  it('deduplicates academics presets', () => {
    const templates = templatesForAcademics({
      presets: ['Code', 'LeetCode', 'Calculus II', 'Calculus II'],
    });
    expect(templates.map(t => t.key)).toEqual(['code', 'leetcode', 'calculus-ii']);
  });
});
