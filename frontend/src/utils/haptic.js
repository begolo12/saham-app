/**
 * haptic.js — lightweight haptic feedback helper.
 *
 * Uses navigator.vibrate() when available (Android Chrome, Edge, Opera, etc.)
 * and silently no-ops on iOS Safari / desktop browsers. The intent is purely
 * cosmetic — visual feedback already exists in the UI; this just adds a tiny
 * physical tap when the platform allows it.
 *
 * Usage:
 *   import haptic from '../utils/haptic';
 *   <button onClick={() => { haptic('light'); doSomething(); }}>Tap</button>
 */

const PATTERNS = {
  light: 10,
  medium: 20,
  heavy: 35,
  success: [12, 30, 12],
  warning: [20, 40, 20],
  error: [40, 30, 40, 30, 40],
};

function getVibrate() {
  if (typeof navigator === 'undefined') return null;
  return typeof navigator.vibrate === 'function' ? navigator.vibrate.bind(navigator) : null;
}

/**
 * Trigger a haptic pattern.
 * @param {'light'|'medium'|'heavy'|'success'|'warning'|'error'|number|number[]} [pattern='light']
 * @returns {boolean} true if vibration was triggered, false otherwise
 */
export function haptic(pattern = 'light') {
  const vibrate = getVibrate();
  if (!vibrate) return false;
  const value = PATTERNS[pattern] != null ? PATTERNS[pattern] : pattern;
  try {
    return vibrate(value);
  } catch {
    return false;
  }
}

export const lightHaptic = () => haptic('light');
export const mediumHaptic = () => haptic('medium');
export const heavyHaptic = () => haptic('heavy');
export const successHaptic = () => haptic('success');
export const warningHaptic = () => haptic('warning');
export const errorHaptic = () => haptic('error');

export default haptic;
