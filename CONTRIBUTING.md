# Contributing to WhiteBit MCP Server

Thank you for your interest in improving WhiteBit MCP Server.

This server's tools are **auto-generated** from the official [WhiteBit Python SDK](https://github.com/whitebit-exchange/whitebit-python). This means the tool list, parameter names, and descriptions are derived programmatically — changes to individual tools should be addressed upstream in the SDK rather than in this repository.

---

## How to Contribute

### Report a Bug

If a tool returns an unexpected result, crashes, or behaves incorrectly:

1. Open an [issue](../../issues/new?template=bug_report.md)
2. Include:
   - The **tool name** (e.g. `spot_trading__create_limit_order`)
   - A **description of the expected vs. actual behavior**
   - The **error message or response** you received (redact credentials)
   - Your **environment**: OS, Docker version or Python version
   - Steps to reproduce

### Request a Feature or Tool

If you'd like a new tool, endpoint, or behavior:

1. Open an [issue](../../issues/new?template=feature_request.md)
2. Describe:
   - What you want the tool or feature to do
   - Which WhiteBit API endpoint it corresponds to (link to [WhiteBit API docs](https://docs.whitebit.com) if applicable)
   - Your use case

> If the missing tool corresponds to a WhiteBit API endpoint that is already present in the Python SDK, it is likely that the tool just needs to be exposed — this can be done quickly.

### Report a Documentation Issue

If something in the README or docs is wrong, outdated, or unclear:

1. Open an [issue](../../issues/new?template=docs.md) describing what needs to be corrected
2. Include the section and a suggested correction if possible

### Ask a Question

For usage questions or integration help, open an [issue](../../issues/new) with the `question` label rather than sending email or a direct message. This keeps answers visible to others with the same question.

---

## What We Do Not Accept

Because tool definitions are auto-generated from the SDK, we do **not** accept pull requests that:

- Manually add, remove, or rename individual tools
- Hardcode tool parameters that should come from the SDK
- Modify generated tool signatures or descriptions

If you believe a tool's signature or description is wrong, please report it as a bug — it is likely an issue in the upstream SDK.

---


## Issue Labels

| Label | Meaning |
|-------|---------|
| `bug` | Something is broken |
| `feature-request` | New tool or capability |
| `docs` | Documentation fix or improvement |
| `question` | Usage or integration question |
| `upstream` | Root cause is in the WhiteBit SDK |
| `wontfix` | Out of scope for this repository |
