# Next Connection Policy Layer Spec

## Status

- Drafted and implemented on 2026-04-13
- Scope: shared planner calendar v1 hardening
- Canonical inputs:
  - `/roadmap.md`
  - `/shared_planner_team_calendar_e_2_e_runbook.md`

## Problem

The current connection policy model already answers:

- who may schedule onto a connection
- which roles may do it
- which item types may do it
- which weddings may do it

What it does not answer cleanly is:

> Should this connection ever be selected automatically by sync policy, or should it only be available when a scheduler explicitly chooses it?

Without a dedicated rule, every writable, allowed connection competes equally in automatic target resolution. That is too coarse for planners who want a calendar to remain writable but never become an implicit default target.

## Decision

Add a new connection-level field:

- `sync_targeting_mode`

Allowed values:

- `automatic_and_manual`

  - The connection may be selected automatically by sync policy.
  - The connection may also be selected by explicit scheduler override.
- `manual_only`

  - The connection is never selected by automatic sync resolution.
  - The connection may still be selected when the scheduler explicitly chooses it.

Default:

- `automatic_and_manual`

## Precedence Model

Connection eligibility must be resolved in this order:

1. Hard connection health and capability gates

   - connection is active
   - connection is writable
   - connection has sync enabled
2. Base scheduler access mode

   - `workspace_default`
   - `owner_only`
   - `owner_and_connection_user`
   - `workspace_permitted`
3. Explicit additive user grants

   - `allowed_scheduler_user_ids`
   - These can widen actor eligibility beyond the base scheduler access mode.
4. Restrictive filters

   - `allowed_scheduler_roles`
   - `allowed_schedule_item_types`
   - `allowed_wedding_ids`
   - These only narrow eligibility; they never widen it.
5. Targeting mode

   - `automatic_and_manual` remains eligible for automatic resolution and explicit override.
   - `manual_only` remains eligible only for explicit override.
6. Schedule-item sync policy

   - `owner_only`
   - `assigned_only`
   - `owner_and_assigned`
   - `custom`
   - This chooses targets only from the remaining eligible connection set.

## Invariants

- Explicit override still wins over automatic selection.
- `manual_only` does not block a valid explicit override.
- `manual_only` must not be chosen implicitly by owner-default or assigned-default fallback logic.
- Existing restrictive filters still apply to explicit overrides.
- The system must fail closed when no eligible target survives the full precedence chain.

## API Surface

Expose `sync_targeting_mode` on:

- calendar connection response payloads
- calendar connection update payloads

Do not expose it on task or meeting payloads. It is a connection policy, not a per-item policy.

## UI Surface

Add a dedicated connection setting in the planner connection-management panel:

- label: `Targeting mode`
- options:
  - `Automatic + manual`
  - `Manual override only`

UI copy must explain:

- automatic selection comes from sync policy
- manual-only connections are still writable, but only when deliberately chosen

## Test Requirements

Must cover:

- manual-only connection excluded from automatic assigned/owner default resolution
- manual-only connection honored for explicit override
- automatic-and-manual connection preserves current default behavior
- additive user grants do not bypass manual-only explicit-selection requirement
- explicit override still fails closed when the connection is blocked by role, item-type, or wedding filters

## Non-Goals

This layer does not implement:

- action-specific policies such as separate create/update/cancel rules
- connection-purpose presets beyond targeting mode
- per-wedding default-routing tables
- connection-class-specific sync strategies

Those require a separate decision-complete spec.
