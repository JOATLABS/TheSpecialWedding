import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import test from 'node:test';


test('root inbox is an additive role-scoped mount', () => {
  const rootInboxPath = 'app/admin/communications/components/RootSupportInboxView.tsx';
  const roleRouterPath = 'app/admin/communications/components/RoleScopedCommunicationsInboxView.tsx';

  assert.equal(existsSync(rootInboxPath), true, 'root support inbox view is missing');
  assert.equal(existsSync(roleRouterPath), true, 'role-scoped inbox mount is missing');

  const pageSource = readFileSync('app/admin/communications/inbox/page.tsx', 'utf8');
  const roleRouterSource = readFileSync(roleRouterPath, 'utf8');

  assert.match(pageSource, /RoleScopedCommunicationsInboxView/);
  assert.match(roleRouterSource, /userProfile\.is_root_admin/);
  assert.match(roleRouterSource, /RootSupportInboxView/);
  assert.match(roleRouterSource, /CommunicationsInboxView/);
});


test('root support inbox requests platform tickets only', () => {
  const rootInboxPath = 'app/admin/communications/components/RootSupportInboxView.tsx';
  assert.equal(existsSync(rootInboxPath), true, 'root support inbox view is missing');
  const source = readFileSync(rootInboxPath, 'utf8');

  assert.match(source, /\/admin\/tickets/);
  assert.doesNotMatch(source, /\/admin\/weddings/);
  assert.doesNotMatch(source, /\/admin\/inbound-emails/);
  assert.doesNotMatch(source, /\/couple-portal/);
  assert.doesNotMatch(source, /\/admin\/sms-tickets/);
});


test('root support inbox renders participant-specific unread state', () => {
  const source = readFileSync(
    'app/admin/communications/components/RootSupportInboxView.tsx',
    'utf8',
  );

  assert.match(source, /unread_count/);
  assert.match(source, /isRead=\{ticket\.is_read\}/);
  assert.match(
    source,
    /if \(loading\) return;[\s\S]*requestedConversation/,
    'deep links must wait for the ticket list so opening an unread ticket decrements the badge exactly once',
  );
});


test('planner inbox retains its existing channel endpoints', () => {
  const source = readFileSync(
    'app/admin/communications/components/CommunicationsInboxView.tsx',
    'utf8',
  );

  assert.match(source, /\/admin\/weddings/);
  assert.match(source, /\/admin\/inbound-emails\/inbox/);
  assert.match(source, /\/couple-portal\/conversations/);
  assert.match(source, /\/admin\/sms-tickets/);
  assert.match(source, /\/admin\/tickets/);
  assert.match(
    source,
    /is_read: ticket\.is_read \?\? true/,
    'planner support tickets must consume the same participant read state returned by the API',
  );
  assert.match(source, /supportTicketUnreadCount/);
});


test('legacy support surfaces are either canonical or explicit redirects', () => {
  assert.equal(existsSync('app/admin/support/page.tsx'), true);
  assert.equal(existsSync('app/admin/communications/inbox/page.tsx'), true);
  assert.equal(existsSync('app/models/support_ticket.py'), false);

  const legacyInbox = readFileSync('app/admin/inbox/page.tsx', 'utf8');
  assert.match(legacyInbox, /redirect/);
  assert.doesNotMatch(legacyInbox, /CommunicationsInboxView/);
});
