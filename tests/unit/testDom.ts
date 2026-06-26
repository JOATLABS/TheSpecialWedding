import { JSDOM } from 'jsdom';

interface DomHandle {
  cleanup: () => void;
}

function copyWindowProperty<K extends keyof typeof globalThis>(
  target: typeof globalThis,
  source: Window & typeof globalThis,
  key: K
) {
  const descriptor = Object.getOwnPropertyDescriptor(source, key);
  if (!descriptor) {
    return;
  }

  Object.defineProperty(target, key, descriptor);
}

export function installDom(): DomHandle {
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    url: 'http://localhost/',
  });

  const { window } = dom;
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
  const originalSelf = Object.getOwnPropertyDescriptor(globalThis, 'self');
  const originalDocument = Object.getOwnPropertyDescriptor(globalThis, 'document');
  const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator');
  const originalLocation = Object.getOwnPropertyDescriptor(globalThis, 'location');
  const originalHTMLElement = Object.getOwnPropertyDescriptor(globalThis, 'HTMLElement');
  const originalNode = Object.getOwnPropertyDescriptor(globalThis, 'Node');
  const originalEvent = Object.getOwnPropertyDescriptor(globalThis, 'Event');
  const originalCustomEvent = Object.getOwnPropertyDescriptor(globalThis, 'CustomEvent');
  const originalMutationObserver = Object.getOwnPropertyDescriptor(globalThis, 'MutationObserver');
  const originalGetComputedStyle = Object.getOwnPropertyDescriptor(globalThis, 'getComputedStyle');
  const originalRequestAnimationFrame = Object.getOwnPropertyDescriptor(globalThis, 'requestAnimationFrame');
  const originalCancelAnimationFrame = Object.getOwnPropertyDescriptor(globalThis, 'cancelAnimationFrame');
  const originalMatchMedia = Object.getOwnPropertyDescriptor(globalThis, 'matchMedia');
  const originalResizeObserver = Object.getOwnPropertyDescriptor(globalThis, 'ResizeObserver');

  Object.defineProperty(globalThis, 'window', { configurable: true, writable: true, value: window });
  Object.defineProperty(globalThis, 'self', { configurable: true, writable: true, value: window });
  Object.defineProperty(globalThis, 'document', { configurable: true, writable: true, value: window.document });
  Object.defineProperty(globalThis, 'navigator', { configurable: true, writable: true, value: window.navigator });
  Object.defineProperty(globalThis, 'location', { configurable: true, writable: true, value: window.location });
  Object.defineProperty(globalThis, 'HTMLElement', { configurable: true, writable: true, value: window.HTMLElement });
  Object.defineProperty(globalThis, 'Node', { configurable: true, writable: true, value: window.Node });
  Object.defineProperty(globalThis, 'Event', { configurable: true, writable: true, value: window.Event });
  Object.defineProperty(globalThis, 'CustomEvent', { configurable: true, writable: true, value: window.CustomEvent });
  Object.defineProperty(globalThis, 'MutationObserver', { configurable: true, writable: true, value: window.MutationObserver });
  Object.defineProperty(globalThis, 'getComputedStyle', {
    configurable: true,
    writable: true,
    value: window.getComputedStyle.bind(window),
  });
  (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

  Object.defineProperty(globalThis, 'requestAnimationFrame', {
    configurable: true,
    writable: true,
    value: (callback: FrameRequestCallback) =>
      setTimeout(() => callback(Date.now()), 0) as unknown as number,
  });

  Object.defineProperty(globalThis, 'cancelAnimationFrame', {
    configurable: true,
    writable: true,
    value: (id: number) => clearTimeout(id),
  });

  Object.defineProperty(globalThis, 'matchMedia', {
    configurable: true,
    writable: true,
    value: ((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })) as typeof globalThis.matchMedia,
  });

  Object.defineProperty(globalThis, 'ResizeObserver', {
    configurable: true,
    writable: true,
    value: class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  });

  if (!window.HTMLElement.prototype.scrollIntoView) {
    window.HTMLElement.prototype.scrollIntoView = () => {};
  }

  if (!('attachEvent' in window.HTMLElement.prototype)) {
    Object.defineProperty(window.HTMLElement.prototype, 'attachEvent', {
      configurable: true,
      writable: true,
      value: () => {},
    });
  }

  if (!('detachEvent' in window.HTMLElement.prototype)) {
    Object.defineProperty(window.HTMLElement.prototype, 'detachEvent', {
      configurable: true,
      writable: true,
      value: () => {},
    });
  }

  for (const key of ['TextEncoder', 'TextDecoder', 'URL', 'Blob', 'File'] as const) {
    if (!(key in globalThis) && key in window) {
      copyWindowProperty(globalThis, window as unknown as Window & typeof globalThis, key);
    }
  }

  return {
    cleanup: () => {
      dom.window.close();
      restoreProperty('window', originalWindow);
      restoreProperty('self', originalSelf);
      restoreProperty('document', originalDocument);
      restoreProperty('navigator', originalNavigator);
      restoreProperty('location', originalLocation);
      restoreProperty('HTMLElement', originalHTMLElement);
      restoreProperty('Node', originalNode);
      restoreProperty('Event', originalEvent);
      restoreProperty('CustomEvent', originalCustomEvent);
      restoreProperty('MutationObserver', originalMutationObserver);
      restoreProperty('getComputedStyle', originalGetComputedStyle);
      restoreProperty('requestAnimationFrame', originalRequestAnimationFrame);
      restoreProperty('cancelAnimationFrame', originalCancelAnimationFrame);
      restoreProperty('matchMedia', originalMatchMedia);
      restoreProperty('ResizeObserver', originalResizeObserver);
    },
  };
}

function restoreProperty(
  key: keyof typeof globalThis,
  descriptor: PropertyDescriptor | undefined
) {
  if (!descriptor) {
    delete (globalThis as Record<string, unknown>)[key as string];
    return;
  }

  Object.defineProperty(globalThis, key, descriptor);
}
