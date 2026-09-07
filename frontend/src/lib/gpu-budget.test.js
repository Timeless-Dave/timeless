import { beforeEach, describe, expect, it } from 'vitest';
import { __resetGpuBudget, getGpuBudget, setEffectsMode } from '@/lib/gpu-budget';

describe('gpu budget', () => {
  beforeEach(() => {
    __resetGpuBudget();
    setEffectsMode('auto');
    __resetGpuBudget();
  });

  it('runs effects when nothing argues against them', () => {
    expect(__resetGpuBudget()).toMatchObject({ quiet: false, reason: null });
  });

  it('never lets the manual switch override reduced motion', () => {
    __resetGpuBudget({ reducedMotion: true });
    setEffectsMode('full');
    expect(getGpuBudget().quiet).toBe(true);
    expect(getGpuBudget().reason).toMatch(/reduced motion/i);
  });

  it('quiets on battery rather than waiting for it to run down', () => {
    const state = __resetGpuBudget({ onBattery: true });
    expect(state.quiet).toBe(true);
    expect(state.reason).toMatch(/on battery/i);
  });

  it('assumes nothing when the battery API is unavailable', () => {
    expect(__resetGpuBudget({ batteryKnown: false }).quiet).toBe(false);
  });

  it('explains measured frame pressure ahead of the other signals', () => {
    expect(__resetGpuBudget({ onBattery: true, pressure: true }).reason).toMatch(/frames were dropping/i);
  });

  it('quiets with data saver', () => {
    expect(__resetGpuBudget({ saveData: true }).reason).toMatch(/data saver/i);
    expect(__resetGpuBudget({ reducedData: true }).reason).toMatch(/data saver/i);
  });

  it('honours an explicit choice in both directions', () => {
    __resetGpuBudget({ onBattery: true });
    setEffectsMode('full');
    expect(getGpuBudget().quiet).toBe(false);
    setEffectsMode('quiet');
    expect(getGpuBudget().quiet).toBe(true);
    setEffectsMode('auto');
    expect(getGpuBudget().quiet).toBe(true);
  });

  it('clears a latched pressure reading when leaving auto', () => {
    __resetGpuBudget({ pressure: true });
    expect(getGpuBudget().quiet).toBe(true);
    setEffectsMode('full');
    expect(getGpuBudget().pressure).toBe(false);
  });
});
