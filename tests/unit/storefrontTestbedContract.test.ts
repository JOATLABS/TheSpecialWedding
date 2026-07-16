import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { describe, it } from "node:test";

const driverPath = "testbed/verify_storefront_frontend_lifecycle.py";
const cleanupPath = "testbed/cleanup_storefront_frontend_lifecycle_state.py";
const playwrightConfigPath = "testbed/playwright.storefront.config.ts";
const playwrightSpecPath = "testbed/storefront_frontend_lifecycle.spec.ts";
const buildDriverPath = "testbed/build_storefront_frontend.py";
const httpsProxyPath = "testbed/storefront_https_proxy.mjs";
const providerHarnessCorePath = "testbed/storefront_provider_harness_core.py";
const storefrontRoutePath = "app/storefront/[domain]/page.tsx";

describe("storefront frontend lifecycle testbed contract", () => {
  it("ships a paired, isolated, run-scoped storefront verifier", () => {
    assert.equal(existsSync(driverPath), true, `${driverPath} must exist`);
    assert.equal(existsSync(cleanupPath), true, `${cleanupPath} must exist`);
    assert.equal(
      existsSync(buildDriverPath),
      true,
      `${buildDriverPath} must exist`,
    );
    assert.equal(
      existsSync(httpsProxyPath),
      true,
      `${httpsProxyPath} must exist`,
    );
    assert.equal(
      existsSync(storefrontRoutePath),
      true,
      `${storefrontRoutePath} must exist`,
    );

    const driver = readFileSync(driverPath, "utf8");
    const cleanup = readFileSync(cleanupPath, "utf8");
    const httpsProxy = readFileSync(httpsProxyPath, "utf8");
    const readme = readFileSync("testbed/README.md", "utf8");
    const envExample = readFileSync("testbed/.env.example", "utf8");
    const rootEnvExample = readFileSync(".env.example", "utf8");
    const productionCompose = readFileSync(
      "docker-compose.production.yml",
      "utf8",
    );
    const gitignore = readFileSync(".gitignore", "utf8");

    assert.match(
      driver,
      /test_planner\+storefront_signature_\{run_id\}@thespecialwedding\.io/,
    );
    assert.match(
      driver,
      /test_planner\+storefront_solo_\{run_id\}@thespecialwedding\.io/,
    );
    assert.match(driver, /assert_safe_target/);
    assert.match(driver, /secrets\.token_hex/);
    assert.match(driver, /STOREFRONT_TESTBED_RUN_MANIFEST/);
    assert.match(driver, /_account_state_fingerprint/);
    assert.match(driver, /account_and_subscription_immutability/);
    assert.match(driver, /01_restricted_upgrade_gate/);
    assert.match(driver, /14_real_custom_url/);
    assert.match(driver, /20_negative_content_filtering/);
    assert.match(driver, /browser_scenario_blockers/);
    assert.match(driver, /TESTBED_STOREFRONT_EXTERNAL_MODE/);
    assert.match(driver, /TESTBED_STOREFRONT_INQUIRY_DELIVERY_MODE/);
    assert.match(driver, /CLOUDFLARE_SAAS_API_TOKEN/);
    assert.match(driver, /TESTBED_STOREFRONT_ALLOWED_CLOUDFLARE_ACCOUNT_IDS/);
    assert.match(driver, /TESTBED_STOREFRONT_ALLOWED_CLOUDFLARE_ZONE_IDS/);
    assert.match(driver, /TESTBED_STOREFRONT_ALLOWED_CNAME_TARGETS/);
    assert.match(driver, /TESTBED_STOREFRONT_ALLOWED_STAGING_BUCKETS/);
    assert.match(driver, /TESTBED_STOREFRONT_ALLOWED_PUBLIC_BUCKETS/);
    assert.match(driver, /\/admin\/storefront\/provider-readiness/);
    assert.match(driver, /inactive_package_name/);
    assert.match(driver, /template_package_name/);
    assert.match(driver, /excluded_service_name/);
    assert.match(driver, /unpublished_review_text/);
    assert.match(driver, /Foreign Planner Package Must Not Render/);
    assert.match(driver, /app\/storefront\/\*\*\/\*\.tsx/);
    assert.match(driver, /subscription_plans"\]\.insert_one/);
    assert.match(driver, /testbed\.storefront_provider_harness:app/);
    assert.match(driver, /--ssl-certfile/);
    assert.match(driver, /NODE_EXTRA_CA_CERTS/);
    assert.match(driver, /"next"\),\s*"start"/);
    assert.match(driver, /certificate_sha256/);
    assert.match(driver, /storefront_https_proxy\.mjs/);
    assert.match(driver, /frontend_upstream_url/);
    assert.match(driver, /latest_https_probe/);
    assert.match(driver, /shutil\.which\("mongod"\)/);
    assert.match(driver, /allow_redirects=False/);
    assert.doesNotMatch(driver, /validate_browser_checkpoint_evidence/);
    assert.doesNotMatch(driver, /input\(/);
    assert.doesNotMatch(driver, /watched_frontend/);

    assert.match(httpsProxy, /https\.createServer/);
    assert.match(httpsProxy, /request\.headers/);
    assert.match(httpsProxy, /STOREFRONT_HTTPS_PROXY_UPSTREAM/);

    assert.match(cleanup, /STOREFRONT_TESTBED_RUN_MANIFEST/);
    assert.match(cleanup, /testbed_run_id/);
    assert.match(cleanup, /storefront_asset_cleanup_receipts/);
    assert.match(cleanup, /email_logs/);
    assert.match(cleanup, /provider_hostname_id/);
    for (const collection of [
      "storefront_inquiries",
      "storefront_domains",
      "storefront_domain_flows",
      "storefront_domain_operations",
      "storefront_domain_instruction_links",
      "storefront_domain_tombstones",
      "storefront_domain_conflict_claims",
      "storefront_domain_operational_metrics",
      "notifications",
      "storefront_settings",
      "storefront_assets",
      "planner_reviews",
      "packages",
      "user_subscriptions",
      "subscription_plans",
      "users",
    ]) {
      assert.match(cleanup, new RegExp(collection));
    }

    assert.match(readme, /verify_storefront_frontend_lifecycle\.py/);
    assert.match(readme, /cleanup_storefront_frontend_lifecycle_state\.py/);
    assert.match(envExample, /TESTBED_STOREFRONT_IMAGE_PATH/);
    assert.match(envExample, /TESTBED_STOREFRONT_CUSTOM_DOMAIN/);
    assert.match(envExample, /TESTBED_STOREFRONT_EXTERNAL_MODE/);
    assert.match(envExample, /TESTBED_STOREFRONT_INQUIRY_DELIVERY_MODE/);
    assert.match(envExample, /TESTBED_STOREFRONT_ARTIFACT_DIR/);
    assert.match(envExample, /TESTBED_STOREFRONT_EXTERNAL_MODE=deterministic/);
    assert.match(
      envExample,
      /TESTBED_STOREFRONT_BACKEND_URL=https:\/\/127\.0\.0\.1:8122/,
    );
    assert.match(
      envExample,
      /TESTBED_STOREFRONT_FRONTEND_URL=https:\/\/127\.0\.0\.1:3122/,
    );
    assert.match(
      envExample,
      /TESTBED_STOREFRONT_FRONTEND_UPSTREAM_URL=http:\/\/127\.0\.0\.1:3123/,
    );
    assert.match(envExample, /STOREFRONT_RUNTIME_REVISION/);
    assert.doesNotMatch(envExample, /TESTBED_STOREFRONT_ALLOW_REMOTE_STAGING/);

    for (const variable of [
      "FRONTEND_URL",
      "STOREFRONT_PLATFORM_DOMAINS",
      "STOREFRONT_CNAME_TARGET",
      "CLOUDFLARE_ACCOUNT_ID",
      "CLOUDFLARE_API_TOKEN",
      "CLOUDFLARE_ZONE_ID",
      "S3_BLOG_BUCKET_NAME",
      "BLOG_MEDIA_DOMAIN",
      "S3_STOREFRONT_STAGING_BUCKET_NAME",
      "STOREFRONT_STAGING_LIFECYCLE_MAX_AGE_DAYS",
      "STOREFRONT_IMAGE_DECODE_CONCURRENCY",
      "STOREFRONT_RUNTIME_REVISION",
    ]) {
      assert.match(rootEnvExample, new RegExp(`^${variable}=`, "m"));
      assert.match(
        productionCompose,
        new RegExp(`- ${variable}=\\$\\{${variable}`),
      );
    }
    assert.match(gitignore, /^testbed\/\.testbed\/$/m);
  });

  it("uses run-scoped Playwright evidence instead of self-attested browser files", () => {
    assert.equal(
      existsSync(playwrightConfigPath),
      true,
      `${playwrightConfigPath} must exist`,
    );
    assert.equal(
      existsSync(playwrightSpecPath),
      true,
      `${playwrightSpecPath} must exist`,
    );

    const driver = readFileSync(driverPath, "utf8");
    const cleanup = readFileSync(cleanupPath, "utf8");
    const config = readFileSync(playwrightConfigPath, "utf8");
    const spec = readFileSync(playwrightSpecPath, "utf8");
    const providerHarnessCore = readFileSync(providerHarnessCorePath, "utf8");
    const productionStorefrontApi = readFileSync("app/api/storefront.py", "utf8");
    const packageJson = JSON.parse(readFileSync("package.json", "utf8")) as {
      scripts?: Record<string, string>;
      devDependencies?: Record<string, string>;
    };

    assert.match(
      packageJson.scripts?.["test:e2e:storefront"] ?? "",
      /verify_storefront_frontend_lifecycle\.py/,
    );
    assert.equal(
      typeof packageJson.devDependencies?.["@axe-core/playwright"],
      "string",
    );

    assert.match(driver, /secrets\.token_hex/);
    assert.match(driver, /STOREFRONT_TESTBED_RUN_MANIFEST/);
    assert.match(driver, /playwright\.storefront\.config\.ts/);
    assert.match(driver, /_PLAYWRIGHT_REQUIRED_RESULTS/);
    assert.match(driver, /_retain_playwright_artifact_manifest/);
    assert.match(driver, /_write_final_artifact_seal/);
    assert.match(driver, /storefront_evidence_source_sha256/);
    assert.match(driver, /SEALED_AFTER_FINAL_MANIFEST/);
    assert.match(driver, /required_scenario_receipt_count/);
    assert.match(driver, /storefront-testbed-build-receipt\.json/);
    assert.match(driver, /subprocess\.run/);
    assert.match(driver, /inactive package/i);
    assert.match(driver, /template package/i);
    assert.match(driver, /excluded service/i);
    assert.match(driver, /unpublished review/i);
    assert.doesNotMatch(driver, /validate_browser_checkpoint_evidence/);
    assert.doesNotMatch(driver, /input\(/);
    assert.doesNotMatch(driver, /watched_frontend/);

    assert.match(cleanup, /STOREFRONT_TESTBED_RUN_MANIFEST/);
    assert.match(cleanup, /run_id/);

    assert.match(config, /webServer:\s*undefined/);
    assert.match(config, /trace:\s*'on'/);
    assert.match(config, /screenshot:\s*'on'/);
    assert.match(config, /video:\s*'on'/);
    assert.match(
      config,
      /ignoreHTTPSErrors:\s*manifest\.provider_mode === 'deterministic'/,
    );
    assert.match(config, /320/);
    assert.match(config, /375/);
    assert.match(config, /390/);
    assert.match(config, /844/);
    assert.match(config, /json/);
    assert.match(config, /junit/);

    assert.match(spec, /@playwright\/test/);
    assert.match(spec, /@axe-core\/playwright/);
    assert.match(spec, /ariaSnapshot/);
    assert.match(spec, /pageerror/);
    assert.match(spec, /requestfailed/);
    assert.match(spec, /console/);
    assert.match(spec, /expectedConsoleErrors:[\s\S]*pathnameSuffix/);
    assert.match(spec, /recordScenarioEvidence/);
    assert.match(spec, /scenario-receipt-/);
    assert.match(spec, /wcag22aa/);
    assert.match(spec, /horizontalOverflow/);
    assert.doesNotMatch(
      spec,
      /attachCheckpoint\(page, testInfo, 'final-state'\)\.catch/,
    );
    assert.match(spec, /Storefront URL/);
    assert.match(spec, /Save for preview/);
    assert.match(spec, /Publish storefront/);
    assert.match(spec, /Send inquiry/);
    assert.match(spec, /raw[- ]json/i);
    assert.match(spec, /provider_mode/);
    assert.match(
      spec,
      /drives deterministic provider state through real FastAPI Mongo routes without external-provider claims/,
    );
    assert.match(spec, /x-storefront-testbed-control-token/);
    assert.match(spec, /Continue to Cloudflare Testbed DNS/);
    assert.match(spec, /external_provider_live/);
    for (const scenario of [
      "04_design_media_internal_preview",
      "06_inquiry_validation_rate_limit_delivery",
      "08_domain_connect_resume_without_dns",
      "09_manual_and_emailed_instructions",
      "10_dns_expected_vs_observed",
      "15_missing_config_friendly_error",
      "16_existing_site_prevalidation",
      "17_activation_state_immutability",
      "18_disconnect_retry_receipt",
      "19_platform_slug_survives_domain_lifecycle",
    ]) {
      assert.match(spec, new RegExp(scenario));
      assert.match(driver, new RegExp(scenario));
    }
    assert.match(spec, /selected-real-media-bytes/);
    assert.match(spec, /png_signature_hex/);
    assert.match(driver, /as passed would be a false positive/);
    assert.match(
      driver,
      /"04_design_media_internal_preview",\s*"BLOCKED"/,
    );
    assert.match(spec, /ownership_only:\s*true/);
    assert.match(spec, /domain-lifecycle-immutability-receipt/);
    assert.match(providerHarnessCore, /authorize_without_dns/);
    assert.match(providerHarnessCore, /include_routing=not payload\.ownership_only/);
    assert.match(providerHarnessCore, /routing-snapshot/);
    assert.doesNotMatch(productionStorefrontApi, /authorize_without_dns/);
    assert.doesNotMatch(productionStorefrontApi, /routing-snapshot/);
    assert.doesNotMatch(spec, /page\.route\([^\n]*custom-domain/);
    assert.doesNotMatch(spec, /Fake DNS provider|frontend-only provider/i);
  });
});
