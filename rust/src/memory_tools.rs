//! Typed MCP memory tools (R3+) with the same semantics as the
//! Python/TypeScript SDKs' convenience methods.
//!
//! Everything here is a thin wrapper over [`VecminClient::mcp_call`]:
//! the server remains the source of truth for validation, authorship
//! (the authenticated agent identity, never a client-supplied id), and
//! the two-phase confirm flow for batch sharing. Optional keys are sent
//! only when `Some`; defaults are applied server-side.

use serde_json::{json, Map, Value};

use crate::client::{ClientError, VecminClient};

/// Arguments for the `store_memory` MCP tool. `text` is the mandatory
/// canonical embedding content; `agent_id` is taken from the client
/// (the server enforces the authenticated identity anyway).
#[derive(Debug, Default, Clone)]
pub struct StoreMemoryArgs {
    /// The memory text to store.
    pub text: String,
    /// Optional metadata as a JSON object.
    pub metadata: Option<Value>,
    /// If true, anchors this memory (persistent_anchor metadata) so it
    /// is exempt from LTSM decay, pruning, and distillation.
    pub is_factual: Option<bool>,
    /// If true, strips any anchor so this outdated memory re-enters
    /// normal LTSM decay.
    pub is_obsolete: Option<bool>,
}

impl StoreMemoryArgs {
    /// Creates arguments with the mandatory text; assign the optional
    /// public fields before passing to [`VecminClient::store_memory`].
    pub fn new(text: impl Into<String>) -> Self {
        Self {
            text: text.into(),
            ..Default::default()
        }
    }
}

/// Arguments for the `search_memory` MCP tool. `query` is mandatory;
/// every other key is sent only when `Some` (defaults are applied
/// server-side: `top_k` = 5).
#[derive(Debug, Default, Clone)]
pub struct SearchMemoryArgs {
    /// The search query text.
    pub query: String,
    /// Number of results to return.
    pub top_k: Option<usize>,
    /// Epoch seconds: only entries created at or after this time.
    pub since_ts: Option<i64>,
    /// Epoch seconds: only entries created at or before this time.
    pub until_ts: Option<i64>,
    /// Only entries whose metadata.tags contains at least one of these
    /// tags (any-of).
    pub tags: Option<Vec<String>>,
    /// Only entries whose text contains this substring (case-insensitive).
    pub keyword: Option<String>,
}

impl SearchMemoryArgs {
    /// Creates arguments with the mandatory query.
    pub fn new(query: impl Into<String>) -> Self {
        Self {
            query: query.into(),
            ..Default::default()
        }
    }
}

/// Arguments for the `list_memories` MCP tool; every key is optional.
#[derive(Debug, Default, Clone)]
pub struct ListMemoriesArgs {
    /// Maximum number of memories to return (server default 20).
    pub limit: Option<usize>,
    /// true = inbox view: only entries other tenants shared with you
    /// (granted collections, own space excluded).
    pub shared_with_me: Option<bool>,
    /// Inbox only: window in hours for the "Recent sharing activity"
    /// summary (server default 168 = 7 days).
    pub since_hours: Option<u64>,
    /// Epoch seconds: only entries created at or after this time.
    pub since_ts: Option<i64>,
    /// Epoch seconds: only entries created at or before this time.
    pub until_ts: Option<i64>,
    /// Only entries whose metadata.tags contains at least one of these
    /// tags (any-of).
    pub tags: Option<Vec<String>>,
    /// Only entries whose text contains this substring (case-insensitive).
    pub keyword: Option<String>,
}

/// One entry of an `import_memories` batch. `text` is mandatory; the
/// other fields ride along only when `Some`.
#[derive(Debug, Default, Clone)]
pub struct ImportMemoryEntry {
    /// The memory text (canonical embedding content).
    pub text: String,
    /// Explicit strong anchoring (default false = weak).
    pub is_factual: Option<bool>,
    /// Optional metadata (e.g. tags, detail, source_ref).
    pub metadata: Option<Value>,
}

impl ImportMemoryEntry {
    /// Creates an entry with the mandatory text.
    pub fn new(text: impl Into<String>) -> Self {
        Self {
            text: text.into(),
            ..Default::default()
        }
    }
}

/// Arguments for the `update_memory_sharing` MCP tool. `shared` is the
/// only mandatory key; the target selector is exactly one of `id`,
/// `ids`, or `scope`.
#[derive(Debug, Clone)]
pub struct UpdateMemorySharingArgs {
    /// true = visible to granted tenants (read-only, full text and
    /// detail), false = private again.
    pub shared: bool,
    /// Single memory vector ID (own collection only).
    pub id: Option<String>,
    /// Batch: explicit list of memory IDs (own collection only).
    pub ids: Option<Vec<String>>,
    /// Batch selector: "all", "tag:<name>", or "query:<text>" (share
    /// by meaning without needing tags).
    pub scope: Option<String>,
    /// Exclude entries whose metadata.tags contains this tag from the
    /// match set.
    pub except_tag: Option<String>,
    /// Exclude these entry IDs from the match set.
    pub except_ids: Option<Vec<String>>,
    /// Field-level exposure for shared entries: "full" (default,
    /// WYSIWYG) or "summary" (detail stripped for grantees).
    pub shared_scope: Option<String>,
    /// Required true to apply a batch exposure of more than one entry
    /// (the first call returns a dry-run summary).
    pub confirm: Option<bool>,
}

impl UpdateMemorySharingArgs {
    /// Creates arguments with the mandatory `shared` flag.
    pub fn new(shared: bool) -> Self {
        Self {
            shared,
            id: None,
            ids: None,
            scope: None,
            except_tag: None,
            except_ids: None,
            shared_scope: None,
            confirm: None,
        }
    }
}

/// Builds the `store_memory` argument object: `text` and `agent_id` are
/// always present, optional keys only when set.
fn store_memory_arguments(args: &StoreMemoryArgs, agent_id: &str) -> Value {
    let mut map = Map::new();
    map.insert("text".to_string(), json!(args.text));
    map.insert("agent_id".to_string(), json!(agent_id));
    if let Some(v) = &args.metadata {
        map.insert("metadata".to_string(), json!(v));
    }
    if let Some(v) = args.is_factual {
        map.insert("is_factual".to_string(), json!(v));
    }
    if let Some(v) = args.is_obsolete {
        map.insert("is_obsolete".to_string(), json!(v));
    }
    Value::Object(map)
}

/// Builds the `search_memory` argument object; optional keys only when set.
fn search_memory_arguments(args: &SearchMemoryArgs) -> Value {
    let mut map = Map::new();
    map.insert("query".to_string(), json!(args.query));
    if let Some(v) = args.top_k {
        map.insert("top_k".to_string(), json!(v));
    }
    if let Some(v) = args.since_ts {
        map.insert("since_ts".to_string(), json!(v));
    }
    if let Some(v) = args.until_ts {
        map.insert("until_ts".to_string(), json!(v));
    }
    if let Some(v) = &args.tags {
        map.insert("tags".to_string(), json!(v));
    }
    if let Some(v) = &args.keyword {
        map.insert("keyword".to_string(), json!(v));
    }
    Value::Object(map)
}

/// Builds the `list_memories` argument object; every key is optional.
fn list_memories_arguments(args: &ListMemoriesArgs) -> Value {
    let mut map = Map::new();
    if let Some(v) = args.limit {
        map.insert("limit".to_string(), json!(v));
    }
    if let Some(v) = args.shared_with_me {
        map.insert("shared_with_me".to_string(), json!(v));
    }
    if let Some(v) = args.since_hours {
        map.insert("since_hours".to_string(), json!(v));
    }
    if let Some(v) = args.since_ts {
        map.insert("since_ts".to_string(), json!(v));
    }
    if let Some(v) = args.until_ts {
        map.insert("until_ts".to_string(), json!(v));
    }
    if let Some(v) = &args.tags {
        map.insert("tags".to_string(), json!(v));
    }
    if let Some(v) = &args.keyword {
        map.insert("keyword".to_string(), json!(v));
    }
    Value::Object(map)
}

/// Builds one `import_memories` entry; optional keys only when set.
fn import_entry_arguments(entry: &ImportMemoryEntry) -> Value {
    let mut map = Map::new();
    map.insert("text".to_string(), json!(entry.text));
    if let Some(v) = entry.is_factual {
        map.insert("is_factual".to_string(), json!(v));
    }
    if let Some(v) = &entry.metadata {
        map.insert("metadata".to_string(), json!(v));
    }
    Value::Object(map)
}

/// Builds the `update_memory_sharing` argument object: `shared` is
/// always present, every other key only when set.
fn update_memory_sharing_arguments(args: &UpdateMemorySharingArgs) -> Value {
    let mut map = Map::new();
    map.insert("shared".to_string(), json!(args.shared));
    if let Some(v) = &args.id {
        map.insert("id".to_string(), json!(v));
    }
    if let Some(v) = &args.ids {
        map.insert("ids".to_string(), json!(v));
    }
    if let Some(v) = &args.scope {
        map.insert("scope".to_string(), json!(v));
    }
    if let Some(v) = &args.except_tag {
        map.insert("except_tag".to_string(), json!(v));
    }
    if let Some(v) = &args.except_ids {
        map.insert("except_ids".to_string(), json!(v));
    }
    if let Some(v) = &args.shared_scope {
        map.insert("shared_scope".to_string(), json!(v));
    }
    if let Some(v) = args.confirm {
        map.insert("confirm".to_string(), json!(v));
    }
    Value::Object(map)
}

impl VecminClient {
    /// Stores a text memory via the `store_memory` MCP tool.
    ///
    /// `agent_id` is taken from the client; the server overrides it
    /// with the authenticated identity bound to the API key. Returns
    /// the server's human-readable report.
    pub fn store_memory(&self, args: StoreMemoryArgs) -> Result<String, ClientError> {
        self.mcp_call(
            "store_memory",
            store_memory_arguments(&args, self.agent_id()),
        )
    }

    /// Semantic search via the `search_memory` MCP tool, with the R3-4
    /// structured filters (`since_ts` / `until_ts` / `tags` / `keyword`).
    pub fn search_memory(&self, args: SearchMemoryArgs) -> Result<String, ClientError> {
        self.mcp_call("search_memory", search_memory_arguments(&args))
    }

    /// Enumerates the caller's own memories (id, full text, metadata),
    /// newest first, via the `list_memories` MCP tool. With
    /// `shared_with_me: true` it returns ONLY entries other tenants
    /// shared with you — the deterministic cross-tenant inbox.
    pub fn list_memories(&self, args: ListMemoriesArgs) -> Result<String, ClientError> {
        self.mcp_call("list_memories", list_memories_arguments(&args))
    }

    /// Corrects a memory in place via the `update_memory` MCP tool:
    /// same id, same anchors, the corrected text re-embedded. `None`
    /// preserves the current anchor grade; `Some(true)` re-grades
    /// strong, `Some(false)` weak. Only the authoring agent may
    /// correct its own entries; every correction appends the previous
    /// text to a bounded history.
    pub fn update_memory(
        &self,
        id: &str,
        text: &str,
        is_factual: Option<bool>,
    ) -> Result<String, ClientError> {
        let mut map = Map::new();
        map.insert("id".to_string(), json!(id));
        map.insert("text".to_string(), json!(text));
        if let Some(v) = is_factual {
            map.insert("is_factual".to_string(), json!(v));
        }
        self.mcp_call("update_memory", Value::Object(map))
    }

    /// Freezes (or unfreezes) one of the caller's memories via the
    /// `freeze_memory` MCP tool: frozen entries are exempt from LTSM
    /// distillation and staleness scavenging — "do not touch this
    /// memory". Advisory on top of anchoring (does not re-grade
    /// strong/weak), reversible any time, author-only.
    pub fn freeze_memory(&self, id: &str, frozen: bool) -> Result<String, ClientError> {
        self.mcp_call("freeze_memory", json!({ "id": id, "frozen": frozen }))
    }

    /// Exports the caller's own memories (author-scoped, own
    /// collection) via the `export_memory` MCP tool, as a
    /// self-contained JSON array (`Some("json")`, the server default)
    /// or human-readable Markdown (`Some("markdown")`). Pass `None` to
    /// use the server default.
    pub fn export_memory(&self, format: Option<&str>) -> Result<String, ClientError> {
        let mut map = Map::new();
        if let Some(f) = format {
            map.insert("format".to_string(), json!(f));
        }
        self.mcp_call("export_memory", Value::Object(map))
    }

    /// Batch-imports prepared entries via the `import_memories` MCP
    /// tool (first-run cold start, cap 200 per call). Every entry goes
    /// through the SAME ingestion core as `store_memory` (anchoring,
    /// gate, LTSM), with per-entry independence and an honest
    /// partial-failure report.
    pub fn import_memories(
        &self,
        entries: Vec<ImportMemoryEntry>,
    ) -> Result<String, ClientError> {
        let memories: Vec<Value> = entries.iter().map(import_entry_arguments).collect();
        self.mcp_call("import_memories", json!({ "memories": memories }))
    }

    /// Flips the cross-tenant sharing flag via the
    /// `update_memory_sharing` MCP tool (owner-side only). Batch
    /// exposure (>1 entry, shared=true) is two-phase: the first call
    /// returns a dry-run summary — re-issue with `confirm: true` to
    /// apply.
    pub fn update_memory_sharing(
        &self,
        args: UpdateMemorySharingArgs,
    ) -> Result<String, ClientError> {
        self.mcp_call(
            "update_memory_sharing",
            update_memory_sharing_arguments(&args),
        )
    }

    /// Lists the distinct tags used across the caller's own memories
    /// via the `list_memory_tags` MCP tool: per-tag counts plus the
    /// number of untagged entries. Useful before sharing by tag.
    pub fn list_memory_tags(&self) -> Result<String, ClientError> {
        self.mcp_call("list_memory_tags", json!({}))
    }

    /// Grants (or revokes) another tenant read access to the caller's
    /// collection via the `set_tenant_grant` MCP tool — owner-side
    /// only, live immediately (no restart). Grantees still only see
    /// entries marked shared via `update_memory_sharing`.
    pub fn set_tenant_grant(
        &self,
        tenant: &str,
        collections: Option<Vec<String>>,
        revoke: Option<bool>,
    ) -> Result<String, ClientError> {
        let mut map = Map::new();
        map.insert("tenant".to_string(), json!(tenant));
        if let Some(v) = collections {
            map.insert("collections".to_string(), json!(v));
        }
        if let Some(v) = revoke {
            map.insert("revoke".to_string(), json!(v));
        }
        self.mcp_call("set_tenant_grant", Value::Object(map))
    }

    /// Owner-side reverse lookup via the `list_tenant_grants` MCP tool:
    /// which tenants currently hold read access to the caller's
    /// collection (shared-entry subset only). Read-only; revoke with
    /// [`VecminClient::set_tenant_grant`] `revoke: true`.
    pub fn list_tenant_grants(&self) -> Result<String, ClientError> {
        self.mcp_call("list_tenant_grants", json!({}))
    }

    /// Guided one-shot share via the `share_with_tenant` MCP tool:
    /// grants the tenant read access AND semantically selects matching
    /// entries of yours, then returns a dry-run with per-entry previews
    /// and sensitivity flags; pass `confirm: true` to apply. Pure
    /// composition of `set_tenant_grant` + `update_memory_sharing`
    /// (scope query). Revoke later with `set_tenant_grant(revoke:true)`.
    pub fn share_with_tenant(
        &self,
        tenant: &str,
        what: &str,
        shared_scope: Option<&str>,
        confirm: Option<bool>,
    ) -> Result<String, ClientError> {
        let mut map = Map::new();
        map.insert("tenant".to_string(), json!(tenant));
        map.insert("what".to_string(), json!(what));
        if let Some(v) = shared_scope {
            map.insert("shared_scope".to_string(), json!(v));
        }
        if let Some(v) = confirm {
            map.insert("confirm".to_string(), json!(v));
        }
        self.mcp_call("share_with_tenant", Value::Object(map))
    }

    /// Manages the standing share rule via the
    /// `update_share_subscription` MCP tool — "future entries matching
    /// <what> go to <tenant>". Pure storage: NEVER shares anything by
    /// itself; pending matches appear via
    /// [`VecminClient::check_share_subscriptions`] and apply only after
    /// an explicit confirm. `remove: true` clears the subscription.
    pub fn update_share_subscription(
        &self,
        what: Option<&str>,
        tenant: Option<&str>,
        shared_scope: Option<&str>,
        remove: Option<bool>,
    ) -> Result<String, ClientError> {
        let mut map = Map::new();
        if let Some(v) = what {
            map.insert("what".to_string(), json!(v));
        }
        if let Some(v) = tenant {
            map.insert("tenant".to_string(), json!(v));
        }
        if let Some(v) = shared_scope {
            map.insert("shared_scope".to_string(), json!(v));
        }
        if let Some(v) = remove {
            map.insert("remove".to_string(), json!(v));
        }
        self.mcp_call("update_share_subscription", Value::Object(map))
    }

    /// Lazily evaluates the standing share subscription via the
    /// `check_share_subscriptions` MCP tool: lists UNSHARED entries of
    /// yours that currently match, with previews and sensitivity flags,
    /// plus the exact one-step confirm command. Read-only — nothing is
    /// shared by checking.
    pub fn check_share_subscriptions(&self) -> Result<String, ClientError> {
        self.mcp_call("check_share_subscriptions", json!({}))
    }

    /// Returns the corrected, scope-guarded memory-protocol rule block
    /// via the `get_memory_rules` MCP tool for a mainstream agent tool
    /// (claude_code | cursor | workbuddy | all), with the exact local
    /// path to write it into. `lang` is "en" (default) or "zh"; pass
    /// `None` for either to use the server defaults.
    pub fn get_memory_rules(
        &self,
        target: Option<&str>,
        lang: Option<&str>,
    ) -> Result<String, ClientError> {
        let mut map = Map::new();
        if let Some(v) = target {
            map.insert("target".to_string(), json!(v));
        }
        if let Some(v) = lang {
            map.insert("lang".to_string(), json!(v));
        }
        self.mcp_call("get_memory_rules", Value::Object(map))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn store_memory_arguments_include_text_and_agent_id() {
        let v = store_memory_arguments(&StoreMemoryArgs::new("hello"), "agent-1");
        assert_eq!(v["text"], json!("hello"));
        assert_eq!(v["agent_id"], json!("agent-1"));
        assert_eq!(v.as_object().unwrap().len(), 2);
    }

    #[test]
    fn store_memory_arguments_send_only_set_optionals() {
        let args = StoreMemoryArgs {
            is_factual: Some(true),
            metadata: Some(json!({ "source": "sdk" })),
            ..StoreMemoryArgs::new("hello")
        };
        let v = store_memory_arguments(&args, "agent-1");
        assert_eq!(v["is_factual"], json!(true));
        assert_eq!(v["metadata"], json!({ "source": "sdk" }));
        assert!(v.get("is_obsolete").is_none(), "unexpected key is_obsolete");
    }

    #[test]
    fn search_memory_arguments_send_query_and_set_filters() {
        let v = search_memory_arguments(&SearchMemoryArgs::new("preferences"));
        assert_eq!(v["query"], json!("preferences"));
        assert_eq!(v.as_object().unwrap().len(), 1);

        let filtered = SearchMemoryArgs {
            top_k: Some(3),
            since_ts: Some(1_700_000_000),
            tags: Some(vec!["work".to_string()]),
            keyword: Some("sla".to_string()),
            ..SearchMemoryArgs::new("preferences")
        };
        let v = search_memory_arguments(&filtered);
        assert_eq!(v["top_k"], json!(3));
        assert_eq!(v["since_ts"], json!(1_700_000_000));
        assert_eq!(v["tags"], json!(["work"]));
        assert_eq!(v["keyword"], json!("sla"));
        assert!(v.get("until_ts").is_none(), "unexpected key until_ts");
    }

    #[test]
    fn list_memories_arguments_are_empty_by_default() {
        let v = list_memories_arguments(&ListMemoriesArgs::default());
        assert_eq!(v, json!({}));
    }

    #[test]
    fn list_memories_arguments_send_set_filters() {
        let args = ListMemoriesArgs {
            limit: Some(10),
            shared_with_me: Some(true),
            until_ts: Some(1_700_000_000),
            ..Default::default()
        };
        let v = list_memories_arguments(&args);
        assert_eq!(v["limit"], json!(10));
        assert_eq!(v["shared_with_me"], json!(true));
        assert_eq!(v["until_ts"], json!(1_700_000_000));
        assert!(v.get("since_ts").is_none(), "unexpected key since_ts");
    }

    #[test]
    fn import_entry_arguments_send_text_plus_set_optionals() {
        let bare = import_entry_arguments(&ImportMemoryEntry::new("plain entry"));
        assert_eq!(bare, json!({ "text": "plain entry" }));

        let rich = ImportMemoryEntry {
            is_factual: Some(true),
            metadata: Some(json!({ "tags": ["a"] })),
            ..ImportMemoryEntry::new("anchored entry")
        };
        let v = import_entry_arguments(&rich);
        assert_eq!(v["is_factual"], json!(true));
        assert_eq!(v["metadata"], json!({ "tags": ["a"] }));
    }

    #[test]
    fn update_memory_sharing_arguments_require_shared() {
        let v = update_memory_sharing_arguments(&UpdateMemorySharingArgs::new(true));
        assert_eq!(v, json!({ "shared": true }));
    }

    #[test]
    fn update_memory_sharing_arguments_send_selectors_and_confirm() {
        let args = UpdateMemorySharingArgs {
            shared: true,
            scope: Some("tag:work".to_string()),
            except_tag: Some("draft".to_string()),
            shared_scope: Some("summary".to_string()),
            confirm: Some(true),
            ..UpdateMemorySharingArgs::new(true)
        };
        let v = update_memory_sharing_arguments(&args);
        assert_eq!(v["shared"], json!(true));
        assert_eq!(v["scope"], json!("tag:work"));
        assert_eq!(v["except_tag"], json!("draft"));
        assert_eq!(v["shared_scope"], json!("summary"));
        assert_eq!(v["confirm"], json!(true));
        assert!(v.get("id").is_none(), "unexpected key id");
    }
}
