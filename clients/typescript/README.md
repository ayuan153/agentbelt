# @seatbelt/client

Typed config helpers to point any OpenAI-compatible TypeScript client at a running [Seatbelt](../../README.md) proxy.

## Install

```bash
npm install @seatbelt/client
```

## Usage

```ts
import OpenAI from 'openai';
import { withSeatbelt } from '@seatbelt/client';

const client = new OpenAI(withSeatbelt(
  { apiKey: process.env.OPENAI_API_KEY },
  { sessionId: user.id }
));

// All requests now route through Seatbelt's proxy (default http://localhost:8088/v1).
// The proxy enforces scope, budget, egress, and tool-use policy — this package just wires the connection.
```

Override the proxy URL via `baseURL` option or the `SEATBELT_BASE_URL` env var.

> **Note:** Seatbelt is language-agnostic — any OpenAI-compatible client in any language can point its `base_url` at the proxy. This package is optional TypeScript DX sugar.
