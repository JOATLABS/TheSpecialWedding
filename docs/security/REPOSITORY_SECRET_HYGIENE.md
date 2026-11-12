# Repository credentials and rewritten history

Keep credentials in the deployment platform's secret store or in a local,
ignored environment file. Commit only empty values or unmistakable placeholders
to example configuration. Do not copy credentials into incident reports,
Postman exports, test defaults, command examples, screenshots, or CI logs.

The credential cleanup rewrote branch and tag history. Existing credentials in
GitHub Actions and hosting secret stores were not removed or changed. Revocation
at each provider is still required for any exposed credential, even after a Git
rewrite; the repository owner reported those credentials already rotated.

## Working after the rewrite

Replace old working copies with a fresh clone:

```sh
git clone https://github.com/LopeWale/WeddingWebApp.git
```

Do not merge or push branches from an old clone: that can restore the exposed
history. If a clone contains unpublished work, review and transfer only the
necessary clean file changes into a fresh clone. Never bundle or upload the old
`.git` directory as a backup artifact.

GitHub controls pull-request refs, cached historical views, and unreachable
server objects. Repository force-pushes cannot remove those copies. GitHub
Support needs the sensitive-data-removal report to finish that cleanup. Forks,
other clones, and previously downloaded artifacts need separate cleanup by
their owners.

## Checks before pushing

The existing detect-secrets pre-commit hook remains enabled. The independent
`Credential scan` workflow scans all fetched Git history on pushes and pull
requests without a paid Gitleaks action or credentials. To run the same check
locally, install Gitleaks 8.30.1 and run:

```sh
gitleaks git . --config .gitleaks.toml \
  --log-opts='--all --full-history' \
  --ignore-gitleaks-allow --redact=100 --no-banner
```

`.gitleaks.toml` extends the default rules. Its exceptions require both an exact
file path and a reviewed literal placeholder, or a hash-only baseline record.
Never add a real credential, whole source directory, or entire commit to an
allowlist. Scanner output must stay redacted, including reports shared in PRs.

The manual Stripe signup driver requires `STRIPE_SECRET_KEY`,
`STRIPE_WEBHOOK_SECRET`, and `ROOT_ADMIN_PASSWORD` from the environment. It exits
before making requests when any of those values is missing. Use isolated test
accounts and test-mode provider credentials for manual lifecycle checks.
