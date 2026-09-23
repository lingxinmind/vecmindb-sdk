//! Media helpers (M4) with the same semantics as the Python SDK's
//! `store_media` / `search_by_image` convenience methods.
//!
//! All vision work happens agent-side: the server runs zero vision
//! models, so callers supply the caption and, for image-to-image search,
//! the CLIP embedding.

use serde_json::{json, Map, Value};

use crate::client::{ClientError, VecminClient};

/// Arguments for the `store_media` MCP tool. `kind` defaults to
/// `"image"` and `is_factual` to `false`; every other key is sent only
/// when `Some`.
#[derive(Debug, Default, Clone)]
pub struct StoreMediaArgs {
    /// Agent-side description; the canonical embedding text. Without a
    /// caption the media stays `pending` and is not text-searchable
    /// until re-stored with the same `media_id` and a caption.
    pub caption: Option<String>,
    /// Base64-encoded blob bytes.
    pub media_data: Option<String>,
    /// Optional stable id; re-uploading replaces the old description
    /// record (G12 upsert).
    pub media_id: Option<String>,
    /// image | audio | video | file.
    pub kind: Option<String>,
    /// MIME type for allow-list validation.
    pub mime: Option<String>,
    /// Path/URL of the original file.
    pub source_ref: Option<String>,
    /// Explicit strong anchoring (e.g. contract scans).
    pub is_factual: Option<bool>,
    /// Optional agent-side CLIP embedding for image-to-image search
    /// (M4); requires `media.clip_collection` server-side.
    pub clip_vector: Option<Vec<f64>>,
}

impl StoreMediaArgs {
    /// Creates empty arguments; assign the public fields you need before
    /// passing to [`VecminClient::store_media`].
    pub fn new() -> Self {
        Self::default()
    }
}

/// Builds the `store_media` argument object: `kind` and `is_factual`
/// are always present, optional keys only when set.
fn store_media_arguments(args: &StoreMediaArgs) -> Value {
    let mut map = Map::new();
    map.insert(
        "kind".to_string(),
        json!(args.kind.clone().unwrap_or_else(|| "image".to_string())),
    );
    map.insert(
        "is_factual".to_string(),
        json!(args.is_factual.unwrap_or(false)),
    );
    if let Some(v) = &args.caption {
        map.insert("caption".to_string(), json!(v));
    }
    if let Some(v) = &args.media_data {
        map.insert("media_data".to_string(), json!(v));
    }
    if let Some(v) = &args.media_id {
        map.insert("media_id".to_string(), json!(v));
    }
    if let Some(v) = &args.mime {
        map.insert("mime".to_string(), json!(v));
    }
    if let Some(v) = &args.source_ref {
        map.insert("source_ref".to_string(), json!(v));
    }
    if let Some(v) = &args.clip_vector {
        map.insert("clip_vector".to_string(), json!(v));
    }
    Value::Object(map)
}

impl VecminClient {
    /// Stores a media item via the `store_media` MCP tool.
    ///
    /// The caption is caller-supplied (the agent generates the
    /// description agent-side; the server runs zero vision models).
    /// Blob-only uploads stay `pending`; re-storing with the same
    /// `media_id` and a caption completes the record (G12 upsert).
    pub fn store_media(&self, args: StoreMediaArgs) -> Result<String, ClientError> {
        self.mcp_call("store_media", store_media_arguments(&args))
    }

    /// Image-to-image search via the `search_media_by_image` MCP tool.
    ///
    /// The CLIP embedding is computed agent-side and searched only in
    /// the auxiliary CLIP space. Requires `media.clip_collection`
    /// server-side (M4, disabled by default).
    ///
    /// `min_score` is an optional cosine floor: `0.0` returns raw
    /// top-k (the text relevance gate does not apply to CLIP space).
    pub fn search_media_by_image(
        &self,
        clip_vector: Vec<f64>,
        top_k: usize,
        min_score: f64,
    ) -> Result<String, ClientError> {
        self.mcp_call(
            "search_media_by_image",
            json!({
                "clip_vector": clip_vector,
                "top_k": top_k,
                "min_score": min_score,
            }),
        )
    }

    /// Convenience form of [`VecminClient::search_media_by_image`]:
    /// runs the agent-side CLIP encoder over the raw image bytes and
    /// delegates. Rust has no keyword arguments, so the precomputed
    /// vector and the image + encoder paths are two functions.
    pub fn search_by_image<F>(
        &self,
        image: &[u8],
        clip_encoder: F,
        top_k: usize,
        min_score: f64,
    ) -> Result<String, ClientError>
    where
        F: FnOnce(&[u8]) -> Vec<f64>,
    {
        let clip_vector = clip_encoder(image);
        self.search_media_by_image(clip_vector, top_k, min_score)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn store_media_arguments_default_to_image_and_not_factual() {
        let v = store_media_arguments(&StoreMediaArgs::new());
        assert_eq!(v["kind"], json!("image"));
        assert_eq!(v["is_factual"], json!(false));
        assert_eq!(v.as_object().unwrap().len(), 2);
    }

    #[test]
    fn store_media_arguments_send_only_set_optionals() {
        let args = StoreMediaArgs {
            caption: Some("a cat photo".to_string()),
            clip_vector: Some(vec![0.1, 0.2, 0.3]),
            ..StoreMediaArgs::new()
        };
        let v = store_media_arguments(&args);
        assert_eq!(v["caption"], json!("a cat photo"));
        assert_eq!(v["clip_vector"], json!([0.1, 0.2, 0.3]));
        for absent in ["media_data", "media_id", "mime", "source_ref"] {
            assert!(v.get(absent).is_none(), "unexpected key {absent}");
        }
    }

    #[test]
    fn store_media_arguments_override_defaults() {
        let args = StoreMediaArgs {
            kind: Some("audio".to_string()),
            is_factual: Some(true),
            ..StoreMediaArgs::new()
        };
        let v = store_media_arguments(&args);
        assert_eq!(v["kind"], json!("audio"));
        assert_eq!(v["is_factual"], json!(true));
    }
}
