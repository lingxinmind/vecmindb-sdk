# vecmindb (Rust client SDK)

VecminDB client SDK for hand-rolled agents — a two-line
`before_turn` / `after_turn` memory loop over the MCP message endpoint.

## Install

```toml
[dependencies]
vecmindb-client = "1.0"
```

## Two-line agent loop

```rust
use vecmindb_client::AgentMemory;

let mem = AgentMemory::connect("http://host:5520", "api-key", "my-agent");

let context = mem.before_turn("customer requirements", 3)?; // "" when gated
let reply = your_llm("customer requirements", &context);
let _memory_id = mem.after_turn("customer requirements", &reply, None)?;
```

- `before_turn` returns a ready-to-inject context block, or an empty
  string for unrelated queries (the server-side relevance gate
  `memory.search_min_score`, default 0.70, filters before the client
  ever sees results).
- `after_turn` stores "question + first 200 chars of the reply" by
  default; pass `Some(AfterTurnOptions { summary: Some("...".into()), ..Default::default() })`
  to override, `AfterTurnOptions::skip()` to skip, `is_factual: true`
  for durable constraints.
- Memory never breaks the agent: on any network failure both calls
  degrade to no-ops (empty context / `Ok(None)`) with a stderr warning.
- Runnable example: `cargo run --example agent_memory`.

## Mainstream tools

This crate targets **custom / self-written agents**. For mainstream
tools (Cursor / Claude Code / WorkBuddy), connect the MCP server in the
tool's settings and say "安装 vecmindb 记忆规则" — the
`get_memory_rules` MCP tool returns the rule block and the agent writes
it for you. See docs/gtm/MCP_GUIDE.md in the main repository.

## Notes

- The client talks JSON-RPC to `/api/v1/mcp/message` over HTTP(S),
  authenticated with `x-api-key`. Blocking API; async variant on the
  roadmap.
- Server-side guarantees (tenant isolation, factuality anchoring, the
  relevance gate) apply identically to every client SDK.
