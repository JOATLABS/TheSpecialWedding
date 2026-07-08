import Link from 'next/link';

import { PolicyCallout, PolicyPageShell, PolicySection } from '@/components/saas/PolicyPageShell';

export default function GoogleCalendarHelpPage() {
  return (
    <PolicyPageShell
      eyebrow="Google Calendar"
      title="Google Calendar Integration"
      description={
        <p>
          The planner calendar keeps meetings and tasks inside The Special Wedding as the
          source of truth, then projects selected schedule items to explicitly connected
          Google calendars for coordination.
        </p>
      }
    >
      <PolicySection title="What the integration does">
        <p>
          Planner owners and permitted team members can connect Google calendars for shared
          scheduling. Meetings created inside The Special Wedding can sync to explicit
          calendar targets selected by the workspace.
        </p>
        <p>
          If no valid target is available, the meeting is still created internally and remains
          visible inside the planner workspace and couple portal. The external sync state is
          marked as not configured instead of guessing another calendar.
        </p>
      </PolicySection>

      <PolicySection title="Visibility and roles">
        <p>
          Shared team visibility is opt-in per connection. Personal external calendars are
          busy/free only by default and show full details only when the planner owner enables
          detail sharing for that connection.
        </p>
        <p>
          Couples do not connect Google Calendar through OAuth in v1. Couple meeting invites
          are delivered by email plus ICS, and meetings remain visible inside the couple
          portal.
        </p>
      </PolicySection>

      <PolicySection title="Google data by scope">
        <p>
          We request the minimum Google scopes needed to operate the planner calendar features
          described here. Data obtained through these scopes is used only inside the connected
          planner workspace to power calendar features and is not used to serve advertisements.
        </p>
        <dl className="space-y-5">
          <div>
            <dt className="break-all font-mono text-xs text-slate-600">
              https://www.googleapis.com/auth/calendar.events
            </dt>
            <dd className="mt-1">
              Used to create, read, update, and delete calendar events on calendars the user
              explicitly connected, so planner-authored meetings can sync and conflict checks
              can run before writing.
            </dd>
          </div>
          <div>
            <dt className="break-all font-mono text-xs text-slate-600">
              https://www.googleapis.com/auth/calendar.calendarlist.readonly
            </dt>
            <dd className="mt-1">
              Used to list calendars on the connected Google account so the planner can choose
              which calendar to read availability from and write events to. We do not modify
              the calendar list itself.
            </dd>
          </div>
          <div>
            <dt className="break-all font-mono text-xs text-slate-600">
              https://www.googleapis.com/auth/userinfo.email
            </dt>
            <dd className="mt-1">
              Used to confirm the connected Google account email and reduce connection mix-ups
              when someone is signed in to multiple Google accounts.
            </dd>
          </div>
        </dl>
      </PolicySection>

      <PolicySection title="Disconnecting Google">
        <p>
          Disconnect from the planner calendar settings at any time. We revoke the integration
          token for the connected account and remove the local connection record. Full deletion
          instructions are available on the{' '}
          <Link className="font-medium text-wedding-rose underline" href="/google-data-deletion">
            Google data deletion page
          </Link>
          .
        </p>
        <PolicyCallout title="Internal schedule stays intact">
          <p>
            The internal meeting record remains authoritative if a Google projection fails,
            is removed, or is disconnected. Reconnecting Google requires an explicit calendar
            target before new external sync writes resume.
          </p>
        </PolicyCallout>
      </PolicySection>
    </PolicyPageShell>
  );
}
