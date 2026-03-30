import { before, describe, it } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { AppRouterContext } from 'next/dist/shared/lib/app-router-context.shared-runtime';
import { PathnameContext } from 'next/dist/shared/lib/hooks-client-context.shared-runtime';

let AuthProvider: typeof import('../../app/contexts/AuthContext').AuthProvider;
let useAuth: typeof import('../../app/contexts/AuthContext').useAuth;
let APIProvider: typeof import('../../app/contexts/APIContext').APIProvider;
let useAPI: typeof import('../../app/contexts/APIContext').useAPI;
let useApi: typeof import('../../app/hooks/useApi').useApi;

const router = {
  back() {},
  forward() {},
  prefetch() {
    return Promise.resolve();
  },
  push() {},
  refresh() {},
  replace() {},
};

function renderWithAdminRouter(element: React.ReactElement): string {
  return renderToStaticMarkup(
    React.createElement(
      AppRouterContext.Provider,
      { value: router as never },
      React.createElement(PathnameContext.Provider, { value: '/admin' }, element)
    )
  );
}

describe('legacy admin context compatibility bridges', () => {
  before(async () => {
    ({ AuthProvider, useAuth } = await import('../../app/contexts/AuthContext'));
    ({ APIProvider, useAPI } = await import('../../app/contexts/APIContext'));
    ({ useApi } = await import('../../app/hooks/useApi'));
  });

  it('AuthProvider still exposes the legacy auth surface', () => {
    function Probe() {
      const { isAuthenticated, isLoading, login, logout, fetchUserProfile } = useAuth();

      return React.createElement('div', {
        'data-state': `${isAuthenticated}|${isLoading}`,
        'data-login': typeof login,
        'data-logout': typeof logout,
        'data-fetch-profile': typeof fetchUserProfile,
      });
    }

    const html = renderWithAdminRouter(
      React.createElement(AuthProvider, null, React.createElement(Probe))
    );

    assert.match(html, /data-state="false\|true"/);
    assert.match(html, /data-login="function"/);
    assert.match(html, /data-logout="function"/);
    assert.match(html, /data-fetch-profile="function"/);
  });

  it('APIProvider still exposes the legacy apiRequest surface', () => {
    function Probe() {
      const { apiRequest } = useAPI();

      return React.createElement('div', {
        'data-api-request': typeof apiRequest,
      });
    }

    const html = renderWithAdminRouter(
      React.createElement(APIProvider, null, React.createElement(Probe))
    );

    assert.match(html, /data-api-request="function"/);
  });

  it('useApi still renders through the legacy bridge provider', () => {
    function Probe() {
      const { request } = useApi();

      return React.createElement('div', {
        'data-request': typeof request,
      });
    }

    const html = renderWithAdminRouter(
      React.createElement(AuthProvider, null, React.createElement(Probe))
    );

    assert.match(html, /data-request="function"/);
  });
});
