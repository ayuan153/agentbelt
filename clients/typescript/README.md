# agentbelt-client

Typed config helpers to point any OpenAI-compatible TypeScript client at a running [Agentbelt](../../README.md) proxy.

## Install

```bash
npm install agentbelt-client
```

## Usage

```ts
import OpenAI from 'openai';
import { withAgentbelt } from 'agentbelt-client';

const client = new OpenAI(withAgentbelt(
  { apiKey: process.env.OPENAI_API_KEY },
  { sessionId: user.id }
));

// All requests now route through Agentbelt's proxy (default http://localhost:8088/v1).
// The proxy enforces scope, budget, egress, and tool-use policy — this package just wires the connection.
```

Override the proxy URL via `baseURL` option or the `AGENTBELT_BASE_URL` env var.

> **Note:** Agentbelt is language-agnostic — any OpenAI-compatible client in any language can point its `base_url` at the proxy. This package is optional TypeScript DX sugar.
