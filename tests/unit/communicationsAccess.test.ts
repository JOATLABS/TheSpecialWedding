import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import type { UserProfile } from '../../app/contexts/AdminContext';


async function loadAccessModule() {
  const accessModule = await import('../../app/admin/utils/communicationsAccess').catch(() => null);
  assert.ok(accessModule, 'centralized frontend communications access projection is missing');
  return accessModule;
}


const rootAdmin: UserProfile = {
  email: 'root@example.com',
  role: 'ROOT_ADMIN',
  is_root_admin: true,
  is_wedding_planner: false,
  is_vendor: false,
};

const planner: UserProfile = {
  email: 'planner@example.com',
  role: 'wedding_planner',
  is_root_admin: false,
  is_wedding_planner: true,
  is_vendor: false,
};


test('root communications projection contains one tab and platform support only', async () => {
  const access = await loadAccessModule();

  assert.deepEqual(access.getVisibleCommunicationsTabs(rootAdmin), ['inbox']);
  assert.deepEqual(access.getInboxSources(rootAdmin), ['platform_support']);
});


test('planner communications projection preserves every existing tab and inbox source', async () => {
  const access = await loadAccessModule();

  assert.deepEqual(access.getVisibleCommunicationsTabs(planner), [
    'inbox',
    'invites',
    'reminders',
    'individual',
    'history',
  ]);
  assert.deepEqual(access.getInboxSources(planner), [
    'inbound_email',
    'couple_messages',
    'guest_sms',
    'platform_support',
  ]);
});


test('root direct planner communications routes redirect to the support inbox', async () => {
  const access = await loadAccessModule();

  assert.equal(access.getRootCommunicationsRedirect('/admin/communications/inbox'), null);
  assert.equal(
    access.getRootCommunicationsRedirect('/admin/communications/invites'),
    '/admin/communications/inbox',
  );
  assert.equal(
    access.getRootCommunicationsRedirect('/admin/communications/reminders'),
    '/admin/communications/inbox',
  );
  assert.equal(
    access.getRootCommunicationsRedirect('/admin/communications/individual'),
    '/admin/communications/inbox',
  );
  assert.equal(
    access.getRootCommunicationsRedirect('/admin/communications/history'),
    '/admin/communications/inbox',
  );
  assert.equal(
    access.getRootCommunicationsRedirect('/admin/reminders'),
    '/admin/communications/inbox',
  );
  assert.equal(access.getRootCommunicationsRedirect('/admin/support'), null);
});


test('runtime navigation and route guard consume the centralized projection', () => {
  const tabsSource = readFileSync(
    'app/admin/communications/components/CommunicationsTabs.tsx',
    'utf8',
  );
  const guardSource = readFileSync('app/components/AdminRouteGuard.tsx', 'utf8');
  const sidebarSource = readFileSync('app/admin/components/Sidebar.tsx', 'utf8');
  const rootNavSource = sidebarSource.match(
    /const adminNavItems:[\s\S]*?const plannerNavItems:/,
  )?.[0] || '';

  assert.match(tabsSource, /getVisibleCommunicationsTabs/);
  assert.match(guardSource, /getRootCommunicationsRedirect/);
  assert.match(
    rootNavSource,
    /name:\s*['"]Communications['"][\s\S]*?href:\s*['"]\/admin\/communications\/inbox['"]/
  );
});


test('communications sender has no hidden legacy tab interface', () => {
  const source = readFileSync(
    'app/admin/communications/components/CommunicationsRemindersView.tsx',
    'utf8',
  );

  assert.doesNotMatch(source, /initialTab/);
  assert.doesNotMatch(source, /legacyActiveTab/);
  assert.doesNotMatch(source, /setLegacyActiveTab/);
});
