# Site Deployment

## Decision

- Site generator: Astro SSG
- Hosting target: Cloudflare Pages
- Fastest path: generate Markdown with Python, sync into Astro content, build static files, deploy `site/dist` with Wrangler

## Rationale

- Astro keeps the site static and zero-cost while still giving proper routing, layouts, and markdown rendering.
- Cloudflare Pages is a good fit for a static archive with global CDN and a simple CLI deploy path.
- GitHub Pages is workable but slower to automate cleanly from this pipeline.
- Vercel would also work, but adds less value than Cloudflare Pages for a plain static archive.

## Commands

Install site dependencies once:

```bash
npm install
npm --prefix site install
```

Build the site from current Markdown output:

```bash
npm run site:build
```

Deploy once Cloudflare auth is configured:

```bash
npm run site:deploy
```

Build automatically after the standard CLI job runs:

```bash
PYTHONPATH=src .venv/bin/python -m cli run
```

Skip the site build explicitly if Node dependencies are not installed yet:

```bash
WEB_REVIVAL_SKIP_SITE_BUILD=1 PYTHONPATH=src .venv/bin/python -m cli run
```

Build and deploy from the Python pipeline once credentials exist:

```bash
WEB_REVIVAL_DEPLOY_SITE=1 PYTHONPATH=src .venv/bin/python -m cli run
```

## Required Environment For Deploy

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- Optional: `CLOUDFLARE_PAGES_PROJECT_NAME`
- Optional: `CLOUDFLARE_PAGES_BRANCH`
- Optional: `SITE_URL`
