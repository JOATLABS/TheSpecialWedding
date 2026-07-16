'use client';

// Focus trap + initial focus + focus return for modal dialogs.
//
// Implements the WAI-ARIA Authoring Practices Modal Dialog pattern's
// keyboard requirements (https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/):
//
//   * On open: focus moves to the first focusable element inside the
//     dialog (or the dialog container itself if none).
//   * Tab from the LAST focusable element wraps to the first.
//   * Shift+Tab from the FIRST focusable element wraps to the last.
//   * On close (cleanup): focus returns to the element that had focus
//     when the dialog opened — typically the trigger button.
//
// Required to satisfy WCAG 2.1 SC 2.1.2 No Keyboard Trap (avoiding the
// inverse — sealing focus inside indefinitely) AND to make the dialog
// usable by keyboard users (the trap itself is required by the dialog
// pattern; Escape is the documented egress).
//
// Usage:
//
//   const dialogRef = useRef<HTMLDivElement>(null);
//   useFocusTrap(dialogRef, open);
//   ...
//   <div ref={dialogRef} role="dialog" aria-modal="true">...</div>

import { RefObject, useEffect } from 'react';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
].join(',');

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
  ).filter((el) => {
    // Skip elements that are disabled, hidden, or zero-size — the
    // browser won't focus them anyway, and including them would let
    // Tab "land" on something invisible inside the trap.
    if (el.hasAttribute('disabled')) return false;
    if (el.tabIndex < 0) return false;
    if (el.closest('[hidden], [aria-hidden="true"]')) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) return false;
    return true;
  });
}

export function useFocusTrap(
  containerRef: RefObject<HTMLElement | null>,
  active: boolean
): void {
  useEffect(() => {
    if (!active) return;
    const container = containerRef.current;
    if (!container) return;

    const previouslyFocused =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;

    // Move initial focus inside the dialog. Prefer the first
    // focusable child; fall back to the container itself made
    // tabbable for one tick.
    const focusables = getFocusableElements(container);
    if (focusables.length > 0) {
      focusables[0].focus();
    } else {
      const prevTabIndex = container.getAttribute('tabindex');
      container.setAttribute('tabindex', '-1');
      container.focus();
      // Restore the prior tabindex (if any) after the focus lands so
      // we don't leave a synthetic ``tabindex="-1"`` on the node.
      if (prevTabIndex === null) {
        // Strip in a microtask so the focus event has fired.
        queueMicrotask(() => container.removeAttribute('tabindex'));
      } else {
        queueMicrotask(() =>
          container.setAttribute('tabindex', prevTabIndex)
        );
      }
    }

    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      const currentFocusables = getFocusableElements(container);
      if (currentFocusables.length === 0) {
        event.preventDefault();
        return;
      }
      const first = currentFocusables[0];
      const last = currentFocusables[currentFocusables.length - 1];
      const activeEl =
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      // Wrap from last → first on Tab, first → last on Shift+Tab.
      // Important: when focus is OUTSIDE the dialog (e.g. browser
      // chrome), reseat it on the first element so Tab can't escape.
      if (!activeEl || !container.contains(activeEl)) {
        event.preventDefault();
        first.focus();
        return;
      }
      if (event.shiftKey && activeEl === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && activeEl === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', onKey, true);

    return () => {
      window.removeEventListener('keydown', onKey, true);
      // Restore focus to the element that had it before we opened.
      // This is the WAI-ARIA pattern's "on close, focus moves back to
      // the element that triggered the dialog" requirement.
      if (
        previouslyFocused &&
        document.contains(previouslyFocused) &&
        typeof previouslyFocused.focus === 'function'
      ) {
        previouslyFocused.focus();
      }
    };
  }, [active, containerRef]);
}
