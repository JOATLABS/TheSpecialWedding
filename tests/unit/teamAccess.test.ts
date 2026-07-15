import assert from 'node:assert/strict';
import test from 'node:test';

import type { UserProfile } from '../../app/contexts/AdminContext';
import {
  canAccessSupportInbox,
  canAccessWeddings,
  canManageGallery,
  canMessageCouples,
  canSendReminders,
  canSendRsvp,
  getPlannerScopedUserId,
} from '../../app/admin/utils/teamAccess';

test('getPlannerScopedUserId keeps planner owners on their own id', () => {
  const profile: UserProfile = {
    id: 'planner-123',
    email: 'planner@example.com',
    role: 'wedding_planner',
    is_root_admin: false,
    is_wedding_planner: true,
    is_vendor: false,
  };

  assert.equal(getPlannerScopedUserId(profile), 'planner-123');
});

test('getPlannerScopedUserId uses parent_planner_id for team-member billing checks', () => {
  const profile: UserProfile = {
    id: 'team-user-456',
    email: 'team@example.com',
    role: 'team_member',
    is_root_admin: false,
    is_wedding_planner: false,
    is_vendor: false,
    is_team_member: true,
    parent_planner_id: 'planner-123',
  };

  assert.equal(getPlannerScopedUserId(profile), 'planner-123');
});

test('getPlannerScopedUserId falls back to the session user id when owner id is absent', () => {
  const profile: UserProfile = {
    id: 'team-user-456',
    email: 'team@example.com',
    role: 'team_member',
    is_root_admin: false,
    is_wedding_planner: false,
    is_vendor: false,
    is_team_member: true,
  };

  assert.equal(getPlannerScopedUserId(profile), 'team-user-456');
  assert.equal(getPlannerScopedUserId(null), null);
});

test('canManageGallery grants planners and root admins gallery access', () => {
  const planner: UserProfile = {
    email: 'planner@example.com',
    role: 'wedding_planner',
    is_root_admin: false,
    is_wedding_planner: true,
    is_vendor: false,
  };
  const rootAdmin: UserProfile = {
    email: 'root@example.com',
    role: 'root_admin',
    is_root_admin: true,
    is_wedding_planner: false,
    is_vendor: false,
  };

  assert.equal(canManageGallery(planner), true);
  assert.equal(canManageGallery(rootAdmin), true);
});

test('canManageGallery follows the independent team permission exactly', () => {
  const teamMember: UserProfile = {
    email: 'team@example.com',
    role: 'team_member',
    is_root_admin: false,
    is_wedding_planner: false,
    is_vendor: false,
    is_team_member: true,
    team_permissions: {
      manage_wedding_settings: true,
      manage_gallery: false,
    },
  };

  assert.equal(canAccessWeddings(teamMember), true);
  assert.equal(canManageGallery(teamMember), false);
  assert.equal(
    canManageGallery({
      ...teamMember,
      team_permissions: {
        ...teamMember.team_permissions,
        manage_gallery: true,
      },
    }),
    true,
  );
  assert.equal(canManageGallery(null), false);
});

test('root admin keeps support inbox access without planner communication capabilities', () => {
  const rootAdmin: UserProfile = {
    email: 'root@example.com',
    role: 'root_admin',
    is_root_admin: true,
    is_wedding_planner: false,
    is_vendor: false,
  };

  assert.equal(canAccessSupportInbox(rootAdmin), true);
  assert.equal(canMessageCouples(rootAdmin), false);
  assert.equal(canSendRsvp(rootAdmin), false);
  assert.equal(canSendReminders(rootAdmin), false);
});

test('wedding planner retains support inbox and planner communication capabilities', () => {
  const planner: UserProfile = {
    email: 'planner@example.com',
    role: 'wedding_planner',
    is_root_admin: false,
    is_wedding_planner: true,
    is_vendor: false,
  };

  assert.equal(canAccessSupportInbox(planner), true);
  assert.equal(canMessageCouples(planner), true);
  assert.equal(canSendRsvp(planner), true);
  assert.equal(canSendReminders(planner), true);
});
