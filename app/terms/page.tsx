import { PolicyPageShell, PolicySection } from '@/components/saas/PolicyPageShell';

export default function TermsPage() {
  return (
    <PolicyPageShell
      eyebrow="Terms"
      title="Terms of Service"
      description={
        <p>
          These terms govern planner accounts, team-member access, couple portals, guest and
          RSVP workflows, vendor and budget tools, contracts, communications, media, payments,
          support, and connected calendar integrations on The Special Wedding.
        </p>
      }
    >
      <PolicySection title="Accounts and roles">
        <p>
          Planner account owners are responsible for the workspaces they create, the team
          members they invite, the weddings they manage, and the permissions they assign.
          Team members may access product areas only to the extent permitted by the planner
          owner&apos;s role and visibility settings.
        </p>
        <p>
          Couple portal users, guests, and vendors may access the specific links, forms,
          contracts, portals, galleries, or messages shared with them. They may not attempt to
          access another workspace, wedding, account, or private record.
        </p>
      </PolicySection>

      <PolicySection title="Workspace records">
        <p>
          Planners are responsible for the accuracy and legality of wedding records, guest
          details, RSVP data, seating assignments, budgets, vendor records, messages, uploaded
          media, contract language, forms, and public website content entered into the
          platform.
        </p>
        <p>
          The platform helps organize and deliver information, but it is not a substitute for
          legal, financial, tax, insurance, venue, vendor, or professional planning advice.
        </p>
      </PolicySection>

      <PolicySection title="Communications">
        <p>
          Users may send email, SMS, in-app messages, invite links, forms, contract links,
          payment links, and calendar invitations through the product. The sending workspace
          is responsible for having the right to contact the recipient and for keeping message
          content appropriate, accurate, and lawful.
        </p>
        <p>
          Delivery may depend on third-party services, recipient settings, carrier behavior,
          email filtering, and correct contact information.
        </p>
      </PolicySection>

      <PolicySection title="Calendars and integrations">
        <p>
          Internal schedule items stored in The Special Wedding are the canonical records.
          External calendars, including Google Calendar, Microsoft 365 / Outlook, iCloud, and
          Exchange/EWS, are downstream projections used for visibility and coordination.
        </p>
        <p>
          When a permitted user connects an external calendar, they authorize the product
          through its integration provider to read calendar metadata and manage calendar
          events for selected calendars so planner-authored meetings can sync according to
          workspace settings. Connections can be revoked from calendar settings.
        </p>
        <p>
          If a projection fails or a connection is revoked, the internal meeting record
          remains authoritative inside the workspace.
        </p>
      </PolicySection>

      <PolicySection title="Vendors, contracts, and payments">
        <p>
          Vendor records, quotes, packages, signatures, payment milestones, and payment links
          are workflow tools for the workspace. Users are responsible for reviewing contract
          language, vendor obligations, payment terms, taxes, refunds, cancellations, and any
          outside agreement before sending or signing.
        </p>
        <p>
          Payment processing, subscriptions, invoices, and payouts may be handled by third-party
          payment providers and are subject to their additional terms.
        </p>
      </PolicySection>

      <PolicySection title="Acceptable use">
        <p>
          Users may not use the product to break the law, infringe rights, harass people, send
          abusive or deceptive communications, upload malicious content, scrape private data,
          bypass permissions, interfere with service operations, or impersonate another person
          or organization.
        </p>
        <p>
          We may limit, suspend, or terminate access where needed to protect users, the
          platform, legal obligations, billing integrity, security, or service availability.
        </p>
      </PolicySection>

      <PolicySection title="Availability and changes">
        <p>
          The service may change over time as features are added, updated, retired, or improved.
          Some features depend on third-party services such as hosting, storage, messaging,
          analytics, payment, calendar, or OAuth providers.
        </p>
        <p>
          Questions about these terms can be sent to{' '}
          <a className="font-medium text-wedding-rose underline" href="mailto:support@thespecialwedding.io">
            support@thespecialwedding.io
          </a>
          .
        </p>
      </PolicySection>
    </PolicyPageShell>
  );
}
