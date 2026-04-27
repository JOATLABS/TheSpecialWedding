import assert from 'node:assert/strict';
import test from 'node:test';

import type { UserProfile } from '../../app/contexts/AdminContext';
import { getPlannerScopedUserId } from '../../app/admin/utils/teamAccess';

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
