This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Eval Workshop

The local Eval Workshop lets developers run either evaluation suite, inspect saved per-case
results, edit the Git-tracked JSONL fixtures, add a diagnostic query as a reviewed case, and open
retrieved evidence at its source page or section.

Start the API from the repository root:

```bash
uv run uvicorn apps.api.main:app --reload --port 8000
```

Then start this application in a second terminal:

```bash
pnpm dev
```

Open `http://localhost:3000`. It targets `http://127.0.0.1:8000` by default; set
`NEXT_PUBLIC_TAXRAG_API_BASE_URL` to choose another local API address. Fixture edits change the
working tree and should be reviewed and committed with Git. This unauthenticated developer tool
must not be exposed outside localhost.

The Question Lab defaults to lexical retrieval and a deterministic fake answer provider. Suite
runs and diagnostics are saved under `var/eval-runs/` with the fixture hash, selected strategy,
source versions, aggregate metrics, and per-case evidence. Semantic retrieval and OpenAI answers
require a confirmation because they send official text to an external API and may incur cost.

PDF evidence links open at the cited page. The HTML sources do not expose persistent element IDs
for every extracted section, so the workshop uses a browser text fragment where available and keeps
the official document URL and section title visible as a fallback.

## Generic Next.js Setup

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
