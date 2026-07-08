import Link from 'next/link';

import { PolicyCallout, PolicyPageShell, PolicySection } from '@/components/saas/PolicyPageShell';

export default function GoogleDataDeletionPage() {
  return (
    <PolicyPageShell
      eyebrow="Data deletion"
      title="Google Data Deletion"
      description={
        <p>
          This page explains how Google Calendar data is disconnected and removed from The
          Special Wedding when a planner or permitted team member stops using the Google
          Calendar integration.
        </p>
      }
    >
      <PolicySection title="How to disconnect">
        <p>
          Sign in to the planner workspace, open calendar settings, and remove the connected
          Google Calendar account or its selected calendar targets. When the last connected
          calendar for that Google account is removed, the app revokes Google access and
          deletes the local connection records used for calendar sync.
        </p>
        <p>
          If you cannot access the workspace, contact{' '}
          <a className="font-medium text-wedding-rose underline" href="mailto:support@thespecialwedding.io">
            support@thespecialwedding.io
          </a>{' '}
          from the account email tied to the workspace.
        </p>
      </PolicySection>

      <PolicySection title="What we remove">
        <p>
          We remove the local calendar connection record, selected calendar metadata, sync
          policy for that connection, health state, and stored integration token associated
          with the disconnected Google account.
        </p>
        <p>
          After removal, future sync attempts fail closed until the planner reconnects a
          valid writable calendar and chooses the desired sync target.
        </p>
      </PolicySection>

      <PolicySection title="What stays">
        <p>
          Meetings, tasks, couple portal timeline records, guest communications, and planner
          audit history remain inside The Special Wedding as workspace records. Google
          Calendar is a projection of planner-authored scheduling records, not the source of
          truth.
        </p>
        <PolicyCallout title="Internal records stay authoritative">
          <p>
            Removing Google access stops future Google Calendar projection. It does not delete
            the planner workspace, wedding timeline, couple portal, guest list, vendor records,
            contracts, invoices, or other platform records unless those are separately deleted
            through their own product flows or support request.
          </p>
        </PolicyCallout>
      </PolicySection>

      <PolicySection title="Related help">
        <p>
          For scope-by-scope Google Calendar details, read the{' '}
          <Link className="font-medium text-wedding-rose underline" href="/google-calendar">
            Google Calendar integration page
          </Link>
          . For broader platform data handling, read the{' '}
          <Link className="font-medium text-wedding-rose underline" href="/privacy">
            privacy policy
          </Link>
          .
        </p>
      </PolicySection>
    </PolicyPageShell>
  );
}
