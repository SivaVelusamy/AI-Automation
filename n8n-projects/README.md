# n8n Projects

This folder contains n8n workflows and related assets used to automate tasks and integrate services. Each workflow is stored as a JSON file that can be imported into an n8n instance (Editor UI, CLI or API).

## Table of Contents
- About
- Prerequisites
- How to import workflows
- Folder structure & naming conventions
- Environment / credentials
- Running and testing locally
- Troubleshooting
- Contributing
- License & contact

## About
These projects host automation workflows compatible with n8n (https://n8n.io). Workflows automate integrations between services, call APIs, transform data, and schedule tasks.

## Prerequisites
- n8n (cloud, desktop, or self-hosted) — recommended version: latest stable.
- Node.js / Docker if running locally.
- Credentials for any services used by the workflows (Google, Slack, Airtable, etc.).

## How to import workflows
You can import the workflow JSON files in several ways:

1. Editor UI
   - Open your n8n Editor (http://localhost:5678 by default).
   - Click the workflow menu (top-right) → Import from file.
   - Select the JSON file from this folder.

2. CLI
   - If you have the n8n CLI available, run:

     n8n import:workflow --input=/path/to/n8n-projects/<workflow-file>.json

   - Adjust the path for where the file is located on your machine.

3. API
   - You can also POST a workflow JSON to the n8n API endpoints (self-hosted instances may need auth). See n8n docs for the exact endpoint for your version.

## Folder structure & naming conventions
- Each workflow is stored as a single JSON file, e.g. `01-sync-contacts.json`.
- Use a numeric prefix to control ordering and make multiple workflows easier to scan.
- Include brief comments at the top of the file name or the workflow description explaining the intent.

Suggested file name pattern:
- `<NN>-<short-description>.json` (e.g. `10-send-daily-report.json`)

## Environment / credentials
- Do not commit secrets (API keys, tokens, passwords) into this repository.
- Use n8n credentials (the Editor UI/credentials system) or environment variables in self-hosted deployments.
- For local testing, use a `.env` file or the n8n credentials manager. Example environment variables you might need:

  - N8N_HOST
  - N8N_PORT
  - HTTP_BASIC_AUTH_USER / HTTP_BASIC_AUTH_PASSWORD (if enabled)
  - SERVICE_API_KEY (example for external services)

## Running and testing locally (Docker)
Quick start with Docker:

docker run -it --rm -p 5678:5678 -v ~/.n8n:/home/node/.n8n n8nio/n8n

After the container starts, open http://localhost:5678 and import a workflow using the Editor UI.

## Troubleshooting
- Workflow import fails: Check the JSON formatting and ensure the file matches the n8n export format for your n8n version.
- Missing credentials: Configure the required credentials in the Editor UI before enabling the workflow.
- Node errors: Inspect the node's log output in n8n and validate input/output data types.

## Contributing
- Add new workflows as individual JSON files following the naming convention above.
- Include a short README or comment in the workflow description explaining what it does, required credentials, and how to test it.
- Open a pull request describing the workflow and any deployment notes.

## License & contact
- See the repository-level LICENSE for license details.
- Questions or issues: open an issue in this repository or contact @SivaVelusamy on GitHub.
