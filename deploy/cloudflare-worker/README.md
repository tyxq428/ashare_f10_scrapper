# Cloudflare remote trigger (phase 2)

The local and GitHub Actions versions do not require Cloudflare.
For a secure web button that dispatches a private GitHub Actions workflow, deploy a Worker and set:

- `GITHUB_TOKEN`: fine-grained token with Actions read/write and repository contents read.
- `GITHUB_OWNER`: repository owner.
- `GITHUB_REPO`: `ashare_f10_scrapper`.

The Worker should proxy `workflow_dispatch` and workflow-status requests so the token never reaches the browser.
A production Worker implementation is intentionally deferred until credentials and the preferred result store (Artifacts or R2) are selected.
