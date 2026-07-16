import assert from "node:assert/strict";
import { after, afterEach, before, describe, it, mock } from "node:test";
import React from "react";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { StorefrontApiTransport } from "../../app/services/storefrontApi";
import { installDom } from "./testDom";

type DomainPanelProps = {
  transport: StorefrontApiTransport;
  canActivate: boolean;
  canManageExisting?: boolean;
  platformUrl: string;
  isPublished: boolean;
  attemptId?: string | null;
  onProviderAuthorize?: (url: string) => void;
  onResumeHandled?: () => void;
};

let DomainPanel: React.ComponentType<DomainPanelProps> | undefined;
let domHandle: ReturnType<typeof installDom> | null = null;

const preflightResponse = {
  hostname: "events.customer.example",
  host_type: "subdomain",
  intent: "migration",
  recommended_flow: "assisted_migration",
  authoritative_dns: {
    zone: "customer.example",
    provider: "cloudflare",
    provider_name: "Cloudflare",
    nameservers: ["anna.ns.cloudflare.com", "bob.ns.cloudflare.com"],
    control_panel_url: "https://dash.cloudflare.com/example/dns",
  },
  registrar: null,
  platform_provider: "Cloudflare for The Special Wedding",
  domain_connect_supported: false,
  domain_connect_provider: "Cloudflare",
  self_service_allowed: false,
  customer_action:
    "Keep the current DNS unchanged and request an assisted cutover.",
  expected_records: [
    {
      type: "TXT",
      name: "_tsw-storefront.events.customer.example",
      relative_host: "_tsw-storefront.events",
      value: null,
      ttl: 300,
      purpose: "application_ownership",
      proxy: null,
    },
  ],
  observed_records: [
    {
      type: "A",
      name: "events.customer.example",
      values: ["203.0.113.5"],
    },
  ],
  conflicts: [
    {
      code: "existing_routing_record",
      record_type: "A",
      values: ["203.0.113.5"],
      message:
        "Existing routing must remain unchanged during assisted migration.",
    },
  ],
};

function domainStatus(overrides: Record<string, unknown> = {}) {
  return {
    attempt_id: "attempt_123",
    revision: 2,
    hostname: "events.customer.example",
    intent: "new",
    application_status: "dns_setup_pending",
    action: "action_required",
    ownership_status: "pending",
    routing_dns_status: "pending",
    provider_hostname_status: "not_started",
    ssl_status: "not_started",
    https_status: "not_started",
    authoritative_dns: preflightResponse.authoritative_dns,
    registrar: null,
    platform_provider: "Cloudflare for The Special Wedding",
    domain_connect_supported: false,
    setup_method: "manual",
    domain_connect_authorized: false,
    expected_records: [
      {
        type: "TXT",
        name: "_tsw-storefront.events.customer.example",
        relative_host: "_tsw-storefront.events",
        value: "tsw-verification=secret-token",
        ttl: 300,
        purpose: "application_ownership",
        proxy: null,
      },
      {
        type: "CNAME",
        name: "events.customer.example",
        relative_host: "events",
        value: "domains.thespecialwedding.com",
        ttl: 300,
        purpose: "storefront_routing",
        proxy: "dns_only",
      },
    ],
    observed_records: [],
    conflicts: [],
    last_checked_at: "2026-07-15T17:00:00Z",
    next_check_at: "2026-07-15T17:05:00Z",
    claim_expires_at: "2026-07-22T17:00:00Z",
    last_error: null,
    cleanup_records: [],
    ...overrides,
  };
}

describe("storefront production custom-domain journey", () => {
  before(async () => {
    domHandle = installDom();
    const importedModule =
      (await import("../../app/admin/components/storefront/CustomDomainManager")) as unknown as Record<
        string,
        unknown
      >;
    DomainPanel = importedModule.CustomDomainPanel as
      | React.ComponentType<DomainPanelProps>
      | undefined;
  });

  afterEach(() => {
    cleanup();
    mock.restoreAll();
  });

  after(() => {
    domHandle?.cleanup();
    domHandle = null;
  });

  it("exports a transport-injected domain panel", () => {
    assert.equal(typeof DomainPanel, "function");
  });

  it("routes Cloudflare-to-Cloudflare migration through ownership proof without self-service provisioning", async () => {
    assert.ok(DomainPanel);
    const calls: Array<{ path: string; method: string; body?: unknown }> = [];
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
      body?: unknown,
    ) => {
      calls.push({ path, method, body });
      if (path.endsWith("/status")) return null as T;
      if (path.endsWith("/preflight")) return preflightResponse as T;
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: false,
      }),
    );

    await waitFor(() => view.getByLabelText(/custom web address/i));
    await user.type(
      view.getByLabelText(/custom web address/i),
      "events.customer.example",
    );
    await user.click(view.getByRole("radio", { name: /already in use/i }));
    await user.click(view.getByRole("button", { name: /check domain/i }));

    await waitFor(() => view.getByText(/cloudflare detected/i));
    view.getByText("Assisted migration recommended");
    view.getByText(/Domain provider/i);
    view.getByText(/Domain seller/i);
    view.getByText(/Storefront service/i);
    assert.equal(view.queryByRole("button", { name: /continue with/i }), null);
    assert.equal(
      view.queryByRole("button", { name: /set up manually/i }),
      null,
    );
    view.getByText(/keep the current DNS unchanged/i);
    view.getByRole("button", { name: /start assisted migration/i });
    assert.deepEqual(calls.at(-1), {
      path: "/admin/storefront/custom-domain/preflight",
      method: "POST",
      body: { domain: "events.customer.example", intent: "migration" },
    });
  });

  it("asks the customer to confirm a shared nameserver family instead of claiming one provider", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>(path: string) => {
      if (path.endsWith("/status")) return null as T;
      if (path.endsWith("/preflight")) {
        return {
          ...preflightResponse,
          authoritative_dns: {
            zone: "customer.example",
            provider: "google_or_squarespace_dns",
            provider_name: "Google Cloud DNS or Squarespace DNS",
            nameservers: ["ns-cloud-a1.googledomains.com"],
            control_panel_url: null,
          },
        } as T;
      }
      throw new Error(`Unexpected request ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() => view.getByLabelText(/custom web address/i));
    await user.type(
      view.getByLabelText(/custom web address/i),
      "events.customer.example",
    );
    await user.click(view.getByRole("button", { name: /check domain/i }));

    await waitFor(() => view.getByText(/confirm where DNS is managed/i));
    view.getByText(/do not identify one customer dashboard with certainty/i);
    assert.equal(view.queryByText(/Google Cloud DNS detected/i), null);
  });

  it("accepts a pasted storefront URL and checks only its web address", async () => {
    assert.ok(DomainPanel);
    const calls: Array<{ path: string; method: string; body?: unknown }> = [];
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
      body?: unknown,
    ) => {
      calls.push({ path, method, body });
      if (path.endsWith("/status")) return null as T;
      if (path.endsWith("/preflight")) {
        return {
          ...preflightResponse,
          intent: "new",
          recommended_flow: "manual",
          self_service_allowed: true,
          customer_action: null,
          conflicts: [],
        } as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    const address = await waitFor(() =>
      view.getByLabelText(/custom web address/i),
    );
    await user.type(
      address,
      "https://events.customer.example/contact?source=planner",
    );
    await user.click(view.getByRole("button", { name: /check domain/i }));

    await waitFor(() => view.getByText(/cloudflare detected/i));
    assert.equal(
      (address as HTMLInputElement).value,
      "events.customer.example",
    );
    assert.deepEqual(calls.at(-1), {
      path: "/admin/storefront/custom-domain/preflight",
      method: "POST",
      body: { domain: "events.customer.example", intent: "new" },
    });
  });

  it("shows pilot availability without offering a false assisted or manual action", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>(path: string) => {
      if (path.endsWith("/status")) return null as T;
      if (path.endsWith("/preflight")) {
        return {
          ...preflightResponse,
          intent: "new",
          recommended_flow: "manual",
          self_service_allowed: false,
          customer_action:
            "Keep using the platform storefront URL while custom-domain onboarding is restricted to the production pilot.",
          conflicts: [],
        } as T;
      }
      throw new Error(`Unexpected request ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() => view.getByLabelText(/custom web address/i));
    await user.type(
      view.getByLabelText(/custom web address/i),
      "events.customer.example",
    );
    await user.click(view.getByRole("button", { name: /check domain/i }));

    await waitFor(() => view.getByText(/custom-domain onboarding is limited/i));
    view.getByText(/restricted to the production pilot/i);
    assert.equal(
      view.queryByRole("button", { name: /start assisted migration/i }),
      null,
    );
    assert.equal(
      view.queryByRole("button", { name: /set up manually/i }),
      null,
    );
    assert.equal(view.queryByRole("button", { name: /continue with/i }), null);
  });

  it("keeps automatic setup planner-first while making exact DNS changes available on demand", async () => {
    assert.ok(DomainPanel);
    const calls: Array<{ path: string; method: string; body?: unknown }> = [];
    const redirects: string[] = [];
    const automaticClaim = domainStatus({
      domain_connect_supported: true,
      domain_connect_provider: "Cloudflare",
      setup_method: "automatic",
      domain_connect_authorized: false,
    });
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
      body?: unknown,
    ) => {
      calls.push({ path, method, body });
      if (path.endsWith("/status")) return null as T;
      if (path.endsWith("/preflight")) {
        return {
          ...preflightResponse,
          intent: "new",
          recommended_flow: "automatic",
          domain_connect_supported: true,
          self_service_allowed: true,
          customer_action: null,
          conflicts: [],
        } as T;
      }
      if (path.endsWith("/claim")) return automaticClaim as T;
      if (path.endsWith("/domain-connect/authorize")) {
        return {
          authorization_url: "https://dns.example/authorize",
          attempt_id: "attempt_123",
        } as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
        onProviderAuthorize: (url) => redirects.push(url),
      }),
    );

    await waitFor(() => view.getByLabelText(/custom web address/i));
    await user.type(
      view.getByLabelText(/custom web address/i),
      "events.customer.example",
    );
    await user.click(view.getByRole("button", { name: /check domain/i }));
    await waitFor(() =>
      view.getByRole("button", { name: /continue with cloudflare/i }),
    );
    view.getByText(/cloudflare can connect this address for you/i);
    view.getByText(/you will sign in securely at cloudflare/i);
    view.getByRole("button", { name: /set up manually instead/i });
    await user.click(
      view.getByRole("button", { name: /continue with cloudflare/i }),
    );

    await waitFor(() =>
      view.getByRole("heading", {
        name: /cloudflare will connect your address/i,
      }),
    );
    view.getByRole("button", { name: /cancel setup/i });
    assert.equal(
      view.queryByRole("button", { name: /disconnect domain/i }),
      null,
    );
    view.getByText(/verify that you control this web address/i);
    view.getByText(/connect it to your planner storefront/i);
    const exactChanges = view
      .getByText(/view exact dns changes/i)
      .closest("details");
    assert.equal(exactChanges?.hasAttribute("open"), false);
    assert.equal(
      calls.some((call) => call.path.endsWith("/domain-connect/authorize")),
      false,
    );
    assert.deepEqual(redirects, []);

    await user.click(view.getByText(/view exact dns changes/i));
    assert.equal(exactChanges?.hasAttribute("open"), true);
    view.getByText("tsw-verification=secret-token");
    await user.click(
      view.getByRole("button", { name: /sign in to cloudflare/i }),
    );
    await waitFor(() =>
      assert.deepEqual(redirects, ["https://dns.example/authorize"]),
    );
    assert.deepEqual(calls.find((call) => call.path.endsWith("/claim"))?.body, {
      domain: "events.customer.example",
      intent: "new",
      setup_method: "automatic",
    });
  });

  it("resumes an authorized automatic connection as simple progress after reload", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>(path: string) => {
      if (path.endsWith("/status")) {
        return domainStatus({
          domain_connect_supported: true,
          domain_connect_provider: "Cloudflare",
          setup_method: "automatic",
          domain_connect_authorized: true,
          application_status: "dns_setup_pending",
          action: "processing",
        }) as T;
      }
      if (path.endsWith("/instructions")) return { links: [] } as T;
      throw new Error(`Unexpected request ${path}`);
    };
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() => view.getByText(/connecting your custom web address/i));
    view.getByText(/you can close this window/i);
    assert.equal(
      view.queryByRole("button", { name: /sign in to cloudflare/i }),
      null,
    );
    assert.equal(view.queryByText(/add these records/i), null);
    const technicalDetails = view
      .getByText(/view technical details/i)
      .closest("details");
    assert.equal(technicalDetails?.hasAttribute("open"), false);
  });

  it("does not offer a stale automatic sign-in after exact template support is withdrawn", async () => {
    assert.ok(DomainPanel);
    const calls: string[] = [];
    const transport: StorefrontApiTransport = async <T,>(path: string) => {
      calls.push(path);
      if (path.endsWith("/status")) {
        return domainStatus({
          setup_method: "automatic",
          domain_connect_supported: true,
          domain_connect_provider: "Cloudflare",
          domain_connect_authorized: false,
          application_status: "claim_pending",
          action: "action_required",
        }) as T;
      }
      if (path.endsWith("/preflight")) {
        return {
          ...preflightResponse,
          intent: "new",
          self_service_allowed: true,
          customer_action:
            "Use the manual instructions to connect this web address.",
          conflicts: [],
          domain_connect_supported: false,
          domain_connect_provider: null,
          recommended_flow: "manual",
        } as T;
      }
      if (path.includes("/instructions?attempt_id=")) return { links: [] } as T;
      throw new Error(`Unexpected request ${path}`);
    };
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() =>
      view.getByText(/automatic setup is not available right now/i),
    );
    assert.equal(
      view.queryByRole("button", { name: /sign in to cloudflare/i }),
      null,
    );
    view.getByRole("button", { name: /use manual setup/i });
    assert.equal(
      calls.filter((path) => path.endsWith("/preflight")).length,
      1,
    );
  });

  it("resumes manual setup as manual even when the provider supports automatic setup", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>(path: string) => {
      if (path.endsWith("/status")) {
        return domainStatus({
          domain_connect_supported: true,
          domain_connect_provider: "Cloudflare",
          setup_method: "manual",
          domain_connect_authorized: false,
        }) as T;
      }
      if (path.endsWith("/instructions")) return { links: [] } as T;
      throw new Error(`Unexpected request ${path}`);
    };
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() => view.getByText(/add these records/i));
    view.getByRole("button", { name: /i've added these records/i });
    assert.equal(
      view.queryByRole("button", { name: /sign in to cloudflare/i }),
      null,
    );
    assert.equal(view.queryByText(/connecting your custom web address/i), null);
  });

  it("always permits manual setup and renders exact records and independent checks", async () => {
    assert.ok(DomainPanel);
    const calls: Array<{ path: string; method: string; body?: unknown }> = [];
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
      body?: unknown,
    ) => {
      calls.push({ path, method, body });
      if (path.endsWith("/status")) return domainStatus() as T;
      if (path.endsWith("/verify")) {
        return domainStatus({
          ownership_status: "verified",
          routing_dns_status: "verified",
        }) as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const copied: string[] = [];
    const user = userEvent.setup({ document: window.document });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async (value: string) => void copied.push(value) },
    });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: false,
      }),
    );

    await waitFor(() => view.getByText(/add these records/i));
    view.getByText("_tsw-storefront.events");
    view.getByText("_tsw-storefront.events.customer.example");
    view.getByText("tsw-verification=secret-token");
    view.getByText(/application ownership/i);
    view.getByText(/DNS only/i);
    for (const label of [
      "Ownership",
      "DNS routing",
      "Provider hostname",
      "SSL certificate",
      "Secure storefront",
    ]) {
      view.getByText(label);
    }
    view.getByText(/next automatic check/i);
    view.getAllByText(/expected/i);
    view.getAllByText(/observed/i);
    view.getByText(/signed HTTPS response from events\.customer\.example/i);
    view.getByText(/storefront is not published/i);
    assert.equal(
      view.queryByRole("button", { name: /retry verification/i }),
      null,
    );
    const platformLink = view.getByRole("link", {
      name: /platform storefront/i,
    });
    assert.equal(platformLink.getAttribute("href"), "/storefront/luxe-events");

    await user.click(view.getByRole("button", { name: /copy all records/i }));
    await waitFor(() => assert.equal(copied.length, 1));
    assert.match(copied[0], /CNAME/);
    assert.match(
      view.getByRole("status").textContent ?? "",
      /copied all DNS records/i,
    );

    await user.click(
      view.getByRole("button", { name: /i've added these records/i }),
    );
    await waitFor(() =>
      assert.deepEqual(
        calls.find(
          (call) =>
            call.path === "/admin/storefront/custom-domain/verify" &&
            call.method === "POST",
        ),
        {
          path: "/admin/storefront/custom-domain/verify",
          method: "POST",
          body: { attempt_id: "attempt_123" },
        },
      ),
    );
  });

  it("withholds storefront routing during migration prevalidation without treating a certificate CNAME as routing", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>() =>
      domainStatus({
        intent: "migration",
        application_status: "migration_prevalidation",
        expected_records: [
          domainStatus().expected_records[0],
          {
            type: "CNAME",
            name: "_acme-challenge.events.customer.example",
            relative_host: "_acme-challenge.events",
            value: "certificate-validation.cloudflare.example",
            ttl: 300,
            purpose: "certificate_validation",
            proxy: "dns_only",
          },
        ],
      }) as T;
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() =>
      view.getByText(/storefront routing is withheld during prevalidation/i),
    );
    view.getByText(/keep the current website route unchanged/i);
    const routingCheck = view.getByText("DNS routing").closest("li");
    assert.ok(routingCheck);
    assert.match(
      routingCheck.textContent ?? "",
      /withheld until ownership and provider prevalidation are complete/i,
    );
    assert.match(
      routingCheck.textContent ?? "",
      /current website routing remains unchanged/i,
    );
    assert.doesNotMatch(
      routingCheck.textContent ?? "",
      /certificate-validation\.cloudflare\.example/i,
    );
  });

  it("selects only the exact storefront routing record when provider validation also uses CNAME", async () => {
    assert.ok(DomainPanel);
    const certificateRecord = {
      type: "CNAME",
      name: "_acme-challenge.events.customer.example",
      relative_host: "_acme-challenge.events",
      value: "certificate-validation.cloudflare.example",
      ttl: 300,
      purpose: "certificate_validation",
      proxy: "dns_only",
    };
    const routingRecord = domainStatus().expected_records[1];
    const transport: StorefrontApiTransport = async <T,>() =>
      domainStatus({
        expected_records: [
          certificateRecord,
          domainStatus().expected_records[0],
          routingRecord,
        ],
      }) as T;
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() => view.getByText(/add these records/i));
    const routingCheck = view.getByText("DNS routing").closest("li");
    assert.ok(routingCheck);
    assert.match(
      routingCheck.textContent ?? "",
      /CNAME events\.customer\.example → domains\.thespecialwedding\.com/i,
    );
    assert.doesNotMatch(
      routingCheck.textContent ?? "",
      /certificate-validation\.cloudflare\.example/i,
    );
  });

  it("labels migration cutover readiness while keeping certificate and storefront routing semantics separate", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>() =>
      domainStatus({
        intent: "migration",
        application_status: "cutover_ready",
        ownership_status: "verified",
        expected_records: [
          {
            type: "CNAME",
            name: "_acme-challenge.events.customer.example",
            relative_host: "_acme-challenge.events",
            value: "certificate-validation.cloudflare.example",
            ttl: 300,
            purpose: "certificate_validation",
            proxy: "dns_only",
          },
          ...domainStatus().expected_records,
        ],
      }) as T;
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() =>
      view.getByText(/storefront routing is ready for cutover/i),
    );
    view.getByText(/shown separately from provider certificate records/i);
    const routingCheck = view.getByText("DNS routing").closest("li");
    assert.ok(routingCheck);
    assert.match(
      routingCheck.textContent ?? "",
      /CNAME events\.customer\.example → domains\.thespecialwedding\.com/i,
    );
    assert.doesNotMatch(
      routingCheck.textContent ?? "",
      /certificate-validation\.cloudflare\.example/i,
    );
  });

  it("uses a fresh private conflict proof without exposing or reassigning the existing owner", async () => {
    assert.ok(DomainPanel);
    const calls: Array<{ path: string; method: string; body?: unknown }> = [];
    const reserved = domainStatus({
      attempt_id: "conflict_attempt_123",
      application_status: "claim_pending",
      action: "add_ownership_record",
      conflict_code: "hostname_reserved",
      expected_records: [
        {
          type: "TXT",
          name: "_tsw-storefront-claim.events.customer.example",
          relative_host: "_tsw-storefront-claim.events",
          value: "tsw-conflict-verification=fresh-claim-token",
          ttl: 300,
          purpose: "conflict_ownership_review",
          proxy: null,
        },
      ],
    });
    const reviewed = {
      ...reserved,
      application_status: "operator_review",
      action: "operator_review",
      ownership_status: "verified",
      observed_records: [
        {
          type: "TXT",
          name: "_tsw-storefront-claim.events.customer.example",
          values: ["tsw-conflict-verification=fresh-claim-token"],
        },
      ],
    };
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
      body?: unknown,
    ) => {
      calls.push({ path, method, body });
      if (path.endsWith("/status")) return reserved as T;
      if (path.endsWith("/verify")) return reviewed as T;
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() => view.getByText(/hostname is already reserved/i));
    view.getByText(/do not reveal who currently uses the hostname/i);
    view.getByText("tsw-conflict-verification=fresh-claim-token");
    assert.equal(view.queryByRole("button", { name: /continue to/i }), null);
    assert.equal(
      view.queryByRole("button", { name: /retry verification/i }),
      null,
    );
    assert.equal(
      view.queryByRole("button", { name: /send instructions/i }),
      null,
    );
    assert.doesNotMatch(
      view.container.textContent ?? "",
      /planner@|owner@|foreign@/i,
    );

    await user.click(
      view.getByRole("button", { name: /i've added the ownership record/i }),
    );
    await waitFor(() => view.getByText(/ownership proof received/i));
    view.getByText(/hostname was not reassigned/i);
    assert.deepEqual(
      calls.find((call) => call.path.endsWith("/verify")),
      {
        path: "/admin/storefront/custom-domain/verify",
        method: "POST",
        body: { attempt_id: "conflict_attempt_123" },
      },
    );
    assert.equal(
      calls.some((call) => call.path.includes("domain-connect")),
      false,
    );
    assert.equal(
      calls.some((call) => call.path.endsWith("/retry")),
      false,
    );
  });

  it("makes check-again enqueue observation and refreshes the open UI while keeping provider retry distinct", async () => {
    assert.ok(DomainPanel);
    let statusReads = 0;
    let observations = 0;
    let retries = 0;
    const actionRequiredStatus = domainStatus({
      application_status: "action_required",
      provider_hostname_status: "active",
      ssl_status: "validation_timed_out",
      last_error: {
        code: "provider_validation_failed",
        message: "The certificate validation attempt needs attention.",
        customer_action:
          "Confirm the validation record and retry provider verification.",
        retryable: true,
        support_id: "SUP-123",
      },
    });
    const refreshedStatus = domainStatus({
      application_status: "hostname_validation",
      ownership_status: "passed",
      routing_dns_status: "passed",
      provider_hostname_status: "active",
      ssl_status: "validation_timed_out",
      last_checked_at: "2026-07-15T17:01:00Z",
      last_error: actionRequiredStatus.last_error,
    });
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (path === "/admin/storefront/custom-domain/status") {
        statusReads += 1;
        return actionRequiredStatus as T;
      }
      if (path.includes("/status?attempt_id=")) {
        statusReads += 1;
        return refreshedStatus as T;
      }
      if (path.endsWith("/retry") && method === "POST") {
        retries += 1;
        return domainStatus() as T;
      }
      if (path.endsWith("/observe") && method === "POST") {
        observations += 1;
        return actionRequiredStatus as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() => view.getByRole("button", { name: /check again/i }));
    await user.click(view.getByRole("button", { name: /check again/i }));
    await waitFor(() => assert.equal(observations, 1));
    await waitFor(() => assert.equal(statusReads, 2), { timeout: 2_000 });
    await waitFor(() => view.getByText(/DNS and connection status refreshed/i));
    assert.ok(view.getAllByText("Passed").length >= 2);
    assert.equal(retries, 0);
    await user.click(view.getByRole("button", { name: /retry verification/i }));
    await waitFor(() => assert.equal(retries, 1));
  });

  it("cancels an in-flight observation timer when the domain panel unmounts", async () => {
    assert.ok(DomainPanel);
    let observations = 0;
    const stableStatus = domainStatus({
      application_status: "hostname_validation",
      ownership_status: "passed",
      routing_dns_status: "passed",
      provider_hostname_status: "active",
      ssl_status: "pending",
    });
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (path.endsWith("/status")) return stableStatus as T;
      if (path.endsWith("/observe") && method === "POST") {
        observations += 1;
        return stableStatus as T;
      }
      if (path.includes("/instructions?attempt_id=")) {
        return { links: [] } as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const originalSetTimeout = window.setTimeout.bind(window);
    const originalClearTimeout = window.clearTimeout.bind(window);
    let observationTimerId: number | null = null;
    let observationTimerCleared = false;
    mock.method(
      window,
      "setTimeout",
      ((handler: TimerHandler, delay?: number, ...args: unknown[]) => {
        const timerId = originalSetTimeout(handler, delay, ...args);
        if (delay === 250) observationTimerId = timerId;
        return timerId;
      }) as typeof window.setTimeout,
    );
    mock.method(
      window,
      "clearTimeout",
      ((timerId?: number) => {
        if (timerId === observationTimerId) observationTimerCleared = true;
        originalClearTimeout(timerId);
      }) as typeof window.clearTimeout,
    );
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await user.click(await view.findByRole("button", { name: /check again/i }));
    await waitFor(() => assert.equal(observations, 1));
    await waitFor(() => assert.notEqual(observationTimerId, null));
    view.unmount();

    assert.equal(observationTimerCleared, true);
  });

  it("normalizes raw FastAPI configuration failures into customer copy", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>(path: string) => {
      if (path.endsWith("/status")) return null as T;
      if (path.endsWith("/preflight")) {
        throw new Error(
          '{"detail":"Storefront custom-domain CNAME target is not configured"}',
        );
      }
      throw new Error(`Unexpected request ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() => view.getByLabelText(/custom web address/i));
    await user.type(
      view.getByLabelText(/custom web address/i),
      "events.customer.example",
    );
    await user.click(view.getByRole("button", { name: /check domain/i }));

    const alert = await view.findByRole("alert");
    assert.match(
      alert.textContent ?? "",
      /custom domains are temporarily unavailable/i,
    );
    assert.match(alert.textContent ?? "", /platform storefront/i);
    assert.doesNotMatch(alert.textContent ?? "", /\{|"detail"/);
  });

  it("shows the current action failure instead of a stale journey error", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (path.includes("/instructions?attempt_id=")) return { links: [] } as T;
      if (path.endsWith("/status")) {
        return domainStatus({
          last_error: {
            code: "ownership_record_missing",
            message: "The current ownership TXT value was not found.",
            customer_action: "Publish the exact current TXT value.",
            retryable: true,
            support_id: "SUP-STALE-1",
          },
        }) as T;
      }
      if (path.endsWith("/verify") && method === "POST") {
        throw new Error(
          '{"error":{"code":"provider_configuration_unavailable","message":"Custom-domain setup is temporarily unavailable.","customer_action":"Keep using your platform storefront URL while support finishes provider setup.","retryable":true,"support_id":"SUP-CURRENT-1"}}',
        );
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() =>
      view.getByText(/current ownership TXT value was not found/i),
    );
    assert.equal(view.queryAllByRole("alert").length, 0);
    await user.click(
      view.getByRole("button", { name: /i've added these records/i }),
    );
    const alerts = await view.findAllByRole("alert");
    assert.equal(alerts.length, 1);
    assert.match(
      alerts[0]?.textContent ?? "",
      /custom-domain setup is temporarily unavailable/i,
    );
    assert.match(alerts[0]?.textContent ?? "", /platform storefront URL/i);
    assert.doesNotMatch(
      alerts[0]?.textContent ?? "",
      /current ownership TXT value was not found/i,
    );
    assert.doesNotMatch(alerts[0]?.textContent ?? "", /SUP-STALE-1/);
  });

  it("promotes a missing DNS result to an alert only after explicit verification", async () => {
    assert.ok(DomainPanel);
    const missingDnsStatus = domainStatus({
      last_error: {
        code: "dns_ownership_not_verified",
        message: "The current ownership TXT value was not found.",
        customer_action:
          "Publish the exact current TXT value, then retry verification.",
        retryable: true,
        support_id: "SUP-DNS-WAIT-1",
      },
    });
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (path.includes("/instructions?attempt_id=")) return { links: [] } as T;
      if (path.endsWith("/status")) return missingDnsStatus as T;
      if (path.endsWith("/verify") && method === "POST")
        return missingDnsStatus as T;
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() =>
      view.getByText(/current ownership TXT value was not found/i),
    );
    assert.equal(view.queryAllByRole("alert").length, 0);
    await user.click(
      view.getByRole("button", { name: /i've added these records/i }),
    );
    const alert = await view.findByRole("alert");
    assert.match(
      alert.textContent ?? "",
      /current ownership TXT value was not found/i,
    );
    assert.match(alert.textContent ?? "", /SUP-DNS-WAIT-1/);
  });

  it("renders operator-review action and support ID from backend truth", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>() =>
      domainStatus({
        application_status: "operator_review",
        action: "operator_review",
        last_error: {
          code: "ambiguous_provider_create",
          message: "We could not safely confirm the provider setup.",
          customer_action: "Contact support before making more DNS changes.",
          retryable: false,
          support_id: "SUP-OPERATOR-1",
        },
      }) as T;
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
        attemptId: "attempt_123",
      }),
    );

    await waitFor(() => view.getByText(/operator review/i));
    view.getByText(/SUP-OPERATOR-1/);
    view.getByText(/contact support before making more DNS changes/i);
    view.getByText(/we resumed your domain setup/i);
    assert.equal(view.queryByText(/attempt_123/i), null);
  });

  it("pauses an ownership-verified Cloudflare migration before provider provisioning", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>() =>
      domainStatus({
        intent: "migration",
        application_status: "operator_review",
        action: "operator_review",
        ownership_status: "verified",
        provider_hostname_status: "not_created",
        expected_records: [domainStatus().expected_records[0]],
        last_error: {
          code: "cloudflare_o2o_migration_requires_assistance",
          message:
            "Ownership is verified and the existing Cloudflare route remains unchanged.",
          customer_action:
            "Request an assisted cutover before changing DNS routing.",
          retryable: false,
          support_id: "SUP-O2O-1",
        },
      }) as T;
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() =>
      view.getByText(/ownership verified — assisted cutover required/i),
    );
    view.getByText(/current Cloudflare routing remains unchanged/i);
    const supportLink = view.getByRole("link", {
      name: /request assisted cutover/i,
    });
    assert.match(supportLink.getAttribute("href") ?? "", /SUP-O2O-1/);
    assert.equal(
      view.queryByRole("button", { name: /I've added these records/i }),
      null,
    );
    assert.equal(view.queryByRole("alert"), null);
  });

  it("completes a resumed Domain Connect authorization once before refreshing status", async () => {
    assert.ok(DomainPanel);
    const calls: Array<{ path: string; method: string; body?: unknown }> = [];
    let resumeHandled = 0;
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
      body?: unknown,
    ) => {
      calls.push({ path, method, body });
      if (path.endsWith("/domain-connect/complete")) {
        return domainStatus({
          application_status: "provider_provisioning",
        }) as T;
      }
      if (path.includes("/status?attempt_id=")) {
        return domainStatus({
          setup_method: "automatic",
          domain_connect_supported: true,
          domain_connect_provider: "Cloudflare",
          domain_connect_authorized: true,
          application_status: "provider_provisioning",
          action: "processing",
        }) as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const props = {
      transport,
      canActivate: true,
      platformUrl: "/storefront/luxe-events",
      isPublished: true,
      attemptId: "attempt_123",
      onResumeHandled: () => {
        resumeHandled += 1;
      },
    };
    const view = render(React.createElement(DomainPanel, props));

    await waitFor(() => view.getByText(/we resumed your domain setup/i));
    view.getByText(/connecting your custom web address/i);
    assert.equal(view.queryByText(/attempt_123/i), null);
    assert.deepEqual(calls.slice(0, 2), [
      {
        path: "/admin/storefront/custom-domain/domain-connect/complete",
        method: "POST",
        body: { attempt_id: "attempt_123" },
      },
      {
        path: "/admin/storefront/custom-domain/status?attempt_id=attempt_123",
        method: "GET",
        body: undefined,
      },
    ]);
    assert.equal(resumeHandled, 1);
    view.rerender(React.createElement(DomainPanel, props));
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    assert.equal(
      calls.filter((call) => call.path.endsWith("/domain-connect/complete"))
        .length,
      1,
    );
  });

  it("treats a consumed one-time Domain Connect callback as status refresh and clears resume state", async () => {
    assert.ok(DomainPanel);
    const calls: string[] = [];
    let resumeHandled = 0;
    const transport: StorefrontApiTransport = async <T,>(path: string) => {
      calls.push(path);
      if (path.endsWith("/domain-connect/complete")) {
        throw new Error(
          JSON.stringify({
            error: {
              code: "domain_connect_flow_consumed",
              message:
                "This one-time Domain Connect flow has already been consumed.",
              customer_action: "Refresh the current domain status.",
              retryable: false,
              support_id: "sfd_consumed_1",
              field_errors: {},
            },
          }),
        );
      }
      if (path.includes("/status?attempt_id=")) return domainStatus() as T;
      throw new Error(`Unexpected request ${path}`);
    };
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
        attemptId: "attempt_123",
        onResumeHandled: () => {
          resumeHandled += 1;
        },
      }),
    );

    await waitFor(() =>
      view.getByText(/one-time authorization was already completed/i),
    );
    assert.deepEqual(calls.slice(0, 2), [
      "/admin/storefront/custom-domain/domain-connect/complete",
      "/admin/storefront/custom-domain/status?attempt_id=attempt_123",
    ]);
    assert.equal(resumeHandled, 1);
    assert.equal(view.queryByRole("alert"), null);
  });

  it("validates and sends exact DNS instructions to the customer DNS contact", async () => {
    assert.ok(DomainPanel);
    const calls: Array<{ path: string; method: string; body?: unknown }> = [];
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
      body?: unknown,
    ) => {
      calls.push({ path, method, body });
      if (path.endsWith("/status")) return domainStatus() as T;
      if (path.includes("/instructions?attempt_id=")) {
        return { links: [] } as T;
      }
      if (path.endsWith("/instructions")) {
        return {
          status: "sent",
          link_id: "sfil_receipt_1",
          state: "active",
          created_at: "2026-07-15T17:05:00Z",
          expires_at: "2026-07-22T17:05:00Z",
          recipient_hint: "d***@e***.com",
        } as T;
      }
      if (path.endsWith("/instructions/sfil_receipt_1")) {
        return { status: "revoked" } as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    const send = await view.findByRole("button", {
      name: /send instructions/i,
    });
    await user.click(send);
    assert.match(
      view.getByRole("alert").textContent ?? "",
      /valid email address/i,
    );
    await user.type(
      view.getByLabelText(/email DNS instructions/i),
      "dns@example.com",
    );
    await user.type(
      view.getByLabelText(/optional note/i),
      "Please add these records.",
    );
    await user.click(send);

    await waitFor(() =>
      assert.equal(
        calls.some(
          (call) =>
            call.path === "/admin/storefront/custom-domain/instructions" &&
            call.method === "POST" &&
            JSON.stringify(call.body) ===
              JSON.stringify({
                attempt_id: "attempt_123",
                email: "dns@example.com",
                note: "Please add these records.",
              }),
        ),
        true,
      ),
    );
    assert.match(
      view.getByRole("status").textContent ?? "",
      /sent to dns@example.com/i,
    );
    assert.match(
      view.getByText(/secure instructions sent/i).textContent ?? "",
      /sent/i,
    );
    assert.match(
      view.getByText(/does not store the full recipient address/i)
        .textContent ?? "",
      /one-way digest.*Resend receives the address/i,
    );
    assert.match(
      view.getByText(/read-only link for d\*\*\*@e\*\*\*\.com/i).textContent ??
        "",
      /cannot publish, activate, transfer, disconnect, or change DNS/i,
    );

    await user.click(
      view.getByRole("button", { name: /revoke instruction link/i }),
    );
    await waitFor(() =>
      assert.equal(
        calls.some(
          (call) =>
            call.path ===
              "/admin/storefront/custom-domain/instructions/sfil_receipt_1" &&
            call.method === "DELETE",
        ),
        true,
      ),
    );
    view.getByText(/instruction link revoked/i);
    assert.equal(
      view.queryByRole("button", { name: /revoke instruction link/i }),
      null,
    );
  });

  it("allows an existing domain to be managed when new activation is unavailable", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>() =>
      domainStatus({
        application_status: "active",
        action: "none",
        ownership_status: "verified",
        routing_dns_status: "verified",
        provider_hostname_status: "active",
        ssl_status: "active",
        https_status: "verified",
      }) as T;
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: false,
        canManageExisting: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() => view.getByText(/custom domain is live/i));
    view.getByRole("button", { name: /disconnect domain/i });
    assert.equal(view.queryByRole("button", { name: /cancel setup/i }), null);
    assert.equal(view.queryByText(/upgrade to add a custom domain/i), null);
  });

  it("fails closed when current domain status cannot be established", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async () => {
      throw new Error(
        '{"error":{"code":"status_unavailable","message":"Status is temporarily unavailable.","customer_action":"Try again shortly.","retryable":true,"support_id":"SUP-STATUS-1"}}',
      );
    };
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        canManageExisting: false,
        platformUrl: "/storefront/luxe-events",
        isPublished: false,
      }),
    );

    const alert = await view.findByRole("alert");
    assert.match(alert.textContent ?? "", /status is temporarily unavailable/i);
    view.getByRole("button", { name: /retry loading domain status/i });
    assert.equal(view.queryByLabelText(/custom web address/i), null);
    assert.equal(view.queryByRole("button", { name: /check domain/i }), null);
  });

  it("keeps diagnostics and disconnect but hides setup mutations after entitlement loss", async () => {
    assert.ok(DomainPanel);
    const calls: Array<{ path: string; method: string }> = [];
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      calls.push({ path, method });
      if (path.includes("/instructions?attempt_id=")) {
        return {
          links: [
            {
              link_id: "sfil_retained_1",
              state: "delivery_failed",
              created_at: "2026-07-15T17:05:00Z",
              expires_at: "2026-07-22T17:05:00Z",
              recipient_hint: "d***@e***.com",
            },
          ],
        } as T;
      }
      if (
        path.endsWith("/instructions/sfil_retained_1") &&
        method === "DELETE"
      ) {
        return { status: "revoked" } as T;
      }
      return domainStatus({
        application_status: "dns_setup_pending",
        action: "add_dns_records",
        ownership_status: "pending",
        routing_dns_status: "pending",
        provider_hostname_status: "not_started",
        ssl_status: "not_started",
        https_status: "not_started",
        last_error: {
          code: "provider_retry",
          message: "Provider retry is available.",
          customer_action: "Retry verification.",
          retryable: true,
          support_id: "SUP-RETRY-1",
        },
      }) as T;
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: false,
        canManageExisting: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: false,
      }),
    );

    await waitFor(() =>
      view.getByText(/setup actions are unavailable on this plan/i),
    );
    view.getByRole("button", { name: /check again/i });
    view.getByRole("button", { name: /cancel setup/i });
    assert.equal(
      view.queryByRole("button", { name: /disconnect domain/i }),
      null,
    );
    await waitFor(() => view.getByText(/d\*\*\*@e\*\*\*\.com/i));
    view.getByText(/email delivery not confirmed/i);
    assert.equal(view.queryByText(/secure instructions sent/i), null);
    const revoke = view.getByRole("button", {
      name: /revoke instruction link for d\*\*\*@e\*\*\*\.com/i,
    });
    assert.equal(view.queryByRole("button", { name: /i've added/i }), null);
    assert.equal(
      view.queryByRole("button", { name: /retry verification/i }),
      null,
    );
    assert.equal(
      view.queryByRole("button", { name: /send instructions/i }),
      null,
    );
    await user.click(revoke);
    await waitFor(() => view.getByText(/instruction link revoked/i));
    assert.equal(
      calls.some(
        (call) =>
          call.path.endsWith("/instructions/sfil_retained_1") &&
          call.method === "DELETE",
      ),
      true,
    );
  });

  it("uses an accessible disconnect confirmation and preserves slug/publication copy", async () => {
    assert.ok(DomainPanel);
    let deleted = false;
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (method === "DELETE") {
        deleted = true;
        return undefined;
      }
      if (path.endsWith("/status")) {
        return domainStatus({
          application_status: "active",
          action: "none",
          ownership_status: "verified",
          routing_dns_status: "verified",
          provider_hostname_status: "active",
          ssl_status: "active",
          https_status: "verified",
          cleanup_records: domainStatus().expected_records,
        }) as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: false,
        canManageExisting: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    const disconnectTrigger = await waitFor(() =>
      view.getByRole("button", { name: /disconnect domain/i }),
    );
    await user.click(disconnectTrigger);
    let confirmation = view.getByRole("dialog", {
      name: /disconnect events\.customer\.example/i,
    });
    assert.match(
      confirmation.textContent ?? "",
      /platform URL.*will not change/i,
    );
    assert.match(
      confirmation.textContent ?? "",
      /publication.*will not change/i,
    );
    view.getByRole("button", { name: /keep domain/i });

    fireEvent.keyDown(confirmation, { key: "Escape" });
    await waitFor(() => assert.equal(view.queryByRole("dialog"), null));
    const restoredTrigger = view.getByRole("button", {
      name: /disconnect domain/i,
    });
    await waitFor(() => assert.ok(document.activeElement === restoredTrigger));
    await user.click(restoredTrigger);
    confirmation = view.getByRole("dialog", {
      name: /disconnect events\.customer\.example/i,
    });
    assert.ok(confirmation);

    await user.click(
      view.getByRole("button", { name: /^disconnect domain$/i, hidden: false }),
    );
    await waitFor(() => assert.equal(deleted, true));
    view.getByText(/connection removed from the special wedding/i);
    view.getByText(/delete these DNS records/i);
  });

  it("restores a persisted disconnect receipt and permits a new setup without replaying lifecycle actions", async () => {
    assert.ok(DomainPanel);
    const calls: Array<{ path: string; method: string }> = [];
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      calls.push({ path, method });
      if (path.endsWith("/status")) {
        return domainStatus({
          attempt_id: null,
          application_status: "disconnected",
          removal_kind: "domain_disconnected",
          action: "remove_dns_records",
          ownership_status: "verified",
          routing_dns_status: "verified",
          provider_hostname_status: "deleted",
          ssl_status: "inactive",
          https_status: "inactive",
          expected_records: [],
          cleanup_records: domainStatus().expected_records,
        }) as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await waitFor(() =>
      view.getByText(/connection removed from the special wedding/i),
    );
    view.getByText(/platform URL and publication setting did not change/i);
    view.getByText(/delete these DNS records/i);
    view.getByText("domains.thespecialwedding.com");
    assert.equal(
      view.queryByRole("button", { name: /disconnect domain/i }),
      null,
    );
    assert.equal(view.queryByRole("button", { name: /i've added/i }), null);
    assert.equal(view.queryByRole("button", { name: /check again/i }), null);
    assert.equal(
      calls.some((call) => call.path.includes("/instructions?attempt_id=")),
      false,
    );

    await user.click(
      view.getByRole("button", { name: /set up another domain/i }),
    );
    await waitFor(() => view.getByLabelText(/custom web address/i));
    assert.equal(
      view.queryByText(/connection removed from the special wedding/i),
      null,
    );
  });

  it("calls an unfinished domain attempt a cancelled setup, including after reload", async () => {
    assert.ok(DomainPanel);
    let cancelled = false;
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (method === "DELETE") {
        cancelled = true;
        return undefined;
      }
      if (path.endsWith("/status")) {
        return domainStatus(
          cancelled
            ? {
                attempt_id: null,
                application_status: "disconnected",
                removal_kind: "setup_cancelled",
                action: "remove_dns_records",
                expected_records: [],
                cleanup_records: domainStatus().expected_records,
              }
            : {
                application_status: "dns_setup_pending",
                setup_method: "automatic",
                domain_connect_supported: true,
                domain_connect_authorized: false,
                cleanup_records: domainStatus().expected_records,
              },
        ) as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await user.click(
      await view.findByRole("button", { name: /cancel setup/i }),
    );
    await user.click(
      view.getByRole("button", { name: /^cancel setup$/i, hidden: false }),
    );
    await waitFor(() => view.getByText(/^setup cancelled$/i));
    assert.equal(
      view.queryByText(/connection removed from the special wedding/i),
      null,
    );

    view.unmount();
    const restored = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );
    await restored.findByText(/^setup cancelled$/i);
    assert.equal(
      restored.queryByText(/connection removed from the special wedding/i),
      null,
    );
  });

  it("keeps persisted disconnect cleanup visible without offering replacement setup when activation is unavailable", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (path.endsWith("/status")) {
        return domainStatus({
          attempt_id: null,
          application_status: "disconnected",
          action: "remove_dns_records",
          provider_hostname_status: "deleted",
          ssl_status: "inactive",
          https_status: "inactive",
          expected_records: [],
          cleanup_records: domainStatus().expected_records,
        }) as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: false,
        canManageExisting: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: false,
      }),
    );

    await waitFor(() =>
      view.getByText(/connection removed from the special wedding/i),
    );
    view.getByText(/delete these DNS records/i);
    assert.equal(
      view.queryByRole("button", { name: /set up another domain/i }),
      null,
    );
    assert.equal(
      view.queryByRole("button", { name: /disconnect domain/i }),
      null,
    );
  });

  it("clears the prior owner disconnect receipt when the authenticated transport changes", async () => {
    assert.ok(DomainPanel);
    const firstTransport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (method === "DELETE") return undefined;
      if (path.endsWith("/status")) {
        return domainStatus({
          attempt_id: null,
          application_status: "active",
          action: "none",
          ownership_status: "verified",
          routing_dns_status: "verified",
          provider_hostname_status: "active",
          ssl_status: "active",
          https_status: "verified",
          cleanup_records: domainStatus().expected_records,
        }) as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const secondTransport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (path.endsWith("/status")) return null as T;
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport: firstTransport,
        canActivate: true,
        platformUrl: "/storefront/first-owner",
        isPublished: true,
      }),
    );

    await user.click(
      await view.findByRole("button", { name: /disconnect domain/i }),
    );
    await user.click(
      view.getByRole("button", { name: /^disconnect domain$/i, hidden: false }),
    );
    await waitFor(() =>
      view.getByText(/connection removed from the special wedding/i),
    );
    view.getByText("events.customer.example");

    view.rerender(
      React.createElement(DomainPanel, {
        transport: secondTransport,
        canActivate: true,
        platformUrl: "/storefront/second-owner",
        isPublished: false,
      }),
    );

    await waitFor(() => view.getByLabelText(/custom web address/i));
    assert.equal(
      view.queryByText(/connection removed from the special wedding/i),
      null,
    );
    assert.equal(view.queryByText("events.customer.example"), null);
  });

  it("closes the confirmation and focuses a visible error when disconnect fails", async () => {
    assert.ok(DomainPanel);
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (method === "DELETE") {
        throw new Error(
          '{"error":{"code":"disconnect_failed","message":"The domain could not be disconnected.","customer_action":"Try again.","retryable":true,"support_id":"SUP-DISCONNECT-1"}}',
        );
      }
      if (path.endsWith("/status")) {
        return domainStatus({
          application_status: "active",
          action: "none",
          ownership_status: "verified",
          routing_dns_status: "verified",
          provider_hostname_status: "active",
          ssl_status: "active",
          https_status: "verified",
        }) as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: false,
        canManageExisting: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await user.click(
      await view.findByRole("button", { name: /disconnect domain/i }),
    );
    await user.click(
      view.getByRole("button", { name: /^disconnect domain$/i, hidden: false }),
    );
    await waitFor(() => assert.equal(view.queryByRole("dialog"), null));
    const alert = view.getByRole("alert");
    assert.match(alert.textContent ?? "", /could not be disconnected/i);
    await waitFor(() =>
      assert.equal(document.activeElement, alert.parentElement),
    );
  });

  it("stops presenting instruction links as active after disconnect intent fails cleanup", async () => {
    assert.ok(DomainPanel);
    let disconnectAttempted = false;
    let postDisconnectInstructionReads = 0;
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (method === "DELETE") {
        disconnectAttempted = true;
        throw new Error(
          '{"error":{"code":"provider_delete_failed","message":"The provider mapping could not be removed.","customer_action":"Retry later.","retryable":true,"support_id":"SUP-DISCONNECT-2"}}',
        );
      }
      if (path.includes("/instructions?attempt_id=")) {
        if (disconnectAttempted) {
          postDisconnectInstructionReads += 1;
          return { links: [] } as T;
        }
        return {
          links: [
            {
              link_id: "sfil_disconnect_1",
              state: "active",
              created_at: "2026-07-15T17:05:00Z",
              expires_at: "2026-07-22T17:05:00Z",
              recipient_hint: "d***@e***.com",
            },
          ],
        } as T;
      }
      if (path.endsWith("/status")) {
        return domainStatus(
          disconnectAttempted
            ? {
                application_status: "disconnect_failed",
                action: "action_required",
                deletion_status: "retry_pending",
                last_error: {
                  code: "provider_delete_failed",
                  message: "The provider mapping could not be removed.",
                  customer_action: "Retry later.",
                  retryable: true,
                  support_id: "SUP-DISCONNECT-2",
                },
              }
            : {
                application_status: "active",
                action: "none",
                ownership_status: "verified",
                routing_dns_status: "verified",
                provider_hostname_status: "active",
                ssl_status: "active",
                https_status: "verified",
              },
        ) as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: false,
        canManageExisting: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await view.findByText(/secure instructions sent/i);
    await user.click(view.getByRole("button", { name: /disconnect domain/i }));
    await user.click(
      view.getByRole("button", { name: /^disconnect domain$/i, hidden: false }),
    );

    await waitFor(() => assert.ok(postDisconnectInstructionReads > 0));
    assert.equal(view.queryByText(/secure instructions sent/i), null);
    assert.equal(
      view.queryByText(/read-only link for d\*\*\*@e\*\*\*\.com/i),
      null,
    );
    const disconnectAlert = view
      .getAllByRole("alert")
      .find((alert) => /could not be removed/i.test(alert.textContent ?? ""));
    assert.ok(disconnectAlert);
    await waitFor(() =>
      assert.equal(document.activeElement, disconnectAlert.parentElement),
    );
  });

  it("reconciles completed background cleanup into the durable disconnect receipt", async () => {
    assert.ok(DomainPanel);
    let backgroundCleanupCompleted = false;
    const transport: StorefrontApiTransport = async <T,>(
      path: string,
      method = "GET",
    ) => {
      if (path.endsWith("/observe") && method === "POST") {
        backgroundCleanupCompleted = true;
        throw new Error(
          '{"error":{"code":"domain_attempt_not_found","message":"The current custom-domain attempt could not be found.","customer_action":"Reload custom-domain status before checking again.","retryable":false,"support_id":"SUP-CLEANUP-1"}}',
        );
      }
      if (path.includes("/instructions?attempt_id=")) {
        return { links: [] } as T;
      }
      if (path.endsWith("/status")) {
        return domainStatus(
          backgroundCleanupCompleted
            ? {
                attempt_id: null,
                application_status: "disconnected",
                removal_kind: "domain_disconnected",
                action: "remove_dns_records",
                expected_records: [],
                cleanup_records: domainStatus().expected_records,
              }
            : {
                application_status: "disconnect_failed",
                action: "action_required",
                deletion_status: "retry_pending",
                last_error: {
                  code: "provider_delete_failed",
                  message: "The provider mapping could not be removed.",
                  customer_action: "Retry later.",
                  retryable: true,
                  support_id: "SUP-CLEANUP-1",
                },
              },
        ) as T;
      }
      throw new Error(`Unexpected request ${method} ${path}`);
    };
    const user = userEvent.setup({ document: window.document });
    const view = render(
      React.createElement(DomainPanel, {
        transport,
        canActivate: true,
        platformUrl: "/storefront/luxe-events",
        isPublished: true,
      }),
    );

    await user.click(await view.findByRole("button", { name: /check again/i }));
    await view.findByText(/connection removed from the special wedding/i);
    assert.equal(
      view.queryByText(/could not check the latest domain status/i),
      null,
    );
  });
});

describe("storefront domain resumable route state", () => {
  it("parses only a safe domain attempt and preserves unrelated query parameters", async () => {
    const routeModule =
      await import("../../app/admin/packages/storefrontRouteState").catch(
        () => null,
      );
    assert.ok(routeModule, "storefrontRouteState module must exist");

    const parsed = routeModule.parseStorefrontRouteState(
      new URLSearchParams(
        "wedding_id=w1&storefront=domain&attempt=attempt_123",
      ),
    );
    assert.deepEqual(parsed, { tab: "domain", attemptId: "attempt_123" });
    assert.equal(
      routeModule.buildStorefrontRouteUrl(
        "/admin/packages",
        new URLSearchParams("wedding_id=w1&filter=active"),
        { tab: "domain", attemptId: "attempt_456" },
      ),
      "/admin/packages?wedding_id=w1&filter=active&storefront=domain&attempt=attempt_456",
    );
    assert.deepEqual(
      routeModule.parseStorefrontRouteState(
        new URLSearchParams(
          "storefront=domain&attempt=https://attacker.example",
        ),
      ),
      { tab: "domain", attemptId: null },
    );
  });
});
