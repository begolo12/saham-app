/* global global */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  haptic,
  lightHaptic,
  mediumHaptic,
  heavyHaptic,
  successHaptic,
  warningHaptic,
  errorHaptic,
} from './haptic';

describe('haptic utility', () => {
  let vibrateSpy;

  beforeEach(() => {
    vibrateSpy = vi.fn().mockReturnValue(true);
    // jsdom provides a navigator object but no vibrate by default
    Object.defineProperty(global.navigator, 'vibrate', {
      value: vibrateSpy,
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('light() calls navigator.vibrate with the light pattern', () => {
    const result = lightHaptic();
    expect(vibrateSpy).toHaveBeenCalledTimes(1);
    expect(vibrateSpy).toHaveBeenCalledWith(10);
    expect(result).toBe(true);
  });

  it('medium() calls navigator.vibrate with the medium pattern', () => {
    mediumHaptic();
    expect(vibrateSpy).toHaveBeenCalledWith(20);
  });

  it('heavy() calls navigator.vibrate with the heavy pattern', () => {
    heavyHaptic();
    expect(vibrateSpy).toHaveBeenCalledWith(35);
  });

  it('success() calls navigator.vibrate with the success pattern', () => {
    successHaptic();
    expect(vibrateSpy).toHaveBeenCalledWith([12, 30, 12]);
  });

  it('warning() calls navigator.vibrate with the warning pattern', () => {
    warningHaptic();
    expect(vibrateSpy).toHaveBeenCalledWith([20, 40, 20]);
  });

  it('errorHaptic() calls navigator.vibrate with the error pattern', () => {
    errorHaptic();
    expect(vibrateSpy).toHaveBeenCalledWith([40, 30, 40, 30, 40]);
  });

  it('haptic() default invocation uses light pattern', () => {
    haptic();
    expect(vibrateSpy).toHaveBeenCalledWith(10);
  });

  it('haptic() accepts a custom numeric pattern', () => {
    haptic(123);
    expect(vibrateSpy).toHaveBeenCalledWith(123);
  });

  it('gracefully no-ops when navigator.vibrate is not available', () => {
    // Delete vibrate from navigator
    Object.defineProperty(global.navigator, 'vibrate', {
      value: undefined,
      configurable: true,
      writable: true,
    });
    expect(() => lightHaptic()).not.toThrow();
    expect(() => errorHaptic()).not.toThrow();
    // No call to undefined vibrate (would throw); helpers just return false
    expect(lightHaptic()).toBe(false);
  });

  it('returns false (and does not throw) when vibrate throws', () => {
    vibrateSpy.mockImplementation(() => { throw new Error('not allowed'); });
    expect(lightHaptic()).toBe(false);
  });

  it('gracefully no-ops on SSR (no navigator)', async () => {
    // Simulate SSR by removing navigator
    const original = global.navigator;
    // @ts-ignore - intentional for test
    delete global.navigator;
    try {
      expect(() => lightHaptic()).not.toThrow();
      expect(lightHaptic()).toBe(false);
    } finally {
      Object.defineProperty(global, 'navigator', {
        value: original,
        configurable: true,
        writable: true,
      });
    }
  });
});
