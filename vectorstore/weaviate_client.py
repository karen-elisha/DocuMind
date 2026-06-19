from __future__ import annotations

from typing import Any, Dict, List

import weaviate
from weaviate.util import generate_uuid5
from weaviate.auth import AuthApiKey

from config import Config


class WeaviateClient:
    """
    Minimal Weaviate wrapper used by ingestion layer.

    Stores chunk objects with required fields:
      - node_id
      - doc_id
      - page
      - type
      - content
      - metadata

    Design goals:
      - Compatible with future Graph Construction / Expansion / Retrieval / Fusion
      - Store metadata needed for filtering and provenance

    Notes:
      - This implementation auto-creates a collection if missing.
      - Embeddings field is included if provided in chunk records.
    """

    def __init__(self):
        # Weaviate client v4 connection.
        # With weaviate-client >=4, use connect_to_weaviate_cloud with:
        # - cluster_url
        # - auth_credentials
        api_key = getattr(Config, "WEAVIATE_API_KEY", "") or ""
        auth_credentials = AuthApiKey(api_key) if api_key else None

        # Weaviate Cloud / v4 connection
        # Disable startup checks because gRPC health checks can be blocked/slow from this environment.
        self.client = weaviate.connect_to_weaviate_cloud(
            cluster_url=Config.WEAVIATE_URL,
            auth_credentials=auth_credentials,
            skip_init_checks=True,
        )

    def close(self) -> None:
        # weaviate-client v4 connection exposes close() in most variants
        try:
            close_fn = getattr(self.client, "close", None)
            if callable(close_fn):
                close_fn()
        except Exception:
            pass

    def _ensure_collection(self, collection_name: str) -> None:
        """
        Ensure the Weaviate class/collection exists without hammering the schema endpoint.

        Strategy:
        1) Check existence via v4 client (preferred).
        2) If missing, create via REST POST /v1/schema with exponential backoff on HTTP 429.
        """
        # 1) Existence check (fast; avoids repeated POST /v1/schema)
        try:
            exists = self.client.collections.exists(collection_name)
            print(f"[Weaviate] collection exists? {exists} (class={collection_name})")
            if exists:
                return
        except Exception as e:
            print(f"[Weaviate] collection exists check failed (will fallback to REST). Error={e!r}")

        # 2) REST schema creation with exponential backoff for 429
        import json
        import time
        from urllib import request as urlrequest
        from urllib.error import HTTPError

        base = Config.WEAVIATE_URL.rstrip("/")
        schema_url = f"{base}/v1/schema"

        api_key = getattr(Config, "WEAVIATE_API_KEY", "") or ""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        schema = {
            "class": collection_name,
            "vectorizer": "none",
            "properties": [
                {"name": "node_id", "dataType": ["text"], "indexFilterable": True, "indexSearchable": True},
                {"name": "doc_id", "dataType": ["text"], "indexFilterable": True, "indexSearchable": True},
                {"name": "page", "dataType": ["int"], "indexFilterable": True, "indexSearchable": False},
                {"name": "type", "dataType": ["text"], "indexFilterable": True, "indexSearchable": True},
                {"name": "content", "dataType": ["text"], "indexFilterable": False, "indexSearchable": True},
                {"name": "metadata", "dataType": ["text"], "indexFilterable": False, "indexSearchable": False},
            ],
        }

        req = urlrequest.Request(
            url=schema_url,
            data=json.dumps(schema).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        max_attempts = 5
        backoff_s = 2

        last_err: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                with urlrequest.urlopen(req, timeout=60) as resp:
                    _ = resp.read()
                print(f"[Weaviate] collection created successfully: class={collection_name}")
                return
            except HTTPError as e:
                last_err = e
                if e.code in (409, 422):
                    print(f"[Weaviate] collection already exists (HTTP {e.code}): class={collection_name}")
                    return
                if e.code == 429:
                    sleep_s = backoff_s * (2 ** (attempt - 1))
                    print(f"[Weaviate] schema create rate-limited (429). attempt={attempt}/{max_attempts}. sleeping={sleep_s}s")
                    time.sleep(sleep_s)
                    continue
                raise
            except Exception as e:
                last_err = e
                sleep_s = backoff_s * (2 ** (attempt - 1))
                print(f"[Weaviate] schema create failed attempt={attempt}/{max_attempts}. sleeping={sleep_s}s. Error={e!r}")
                time.sleep(sleep_s)

        raise RuntimeError(f"Failed to ensure Weaviate class exists: {collection_name}. LastError={last_err!r}")

    def upsert_chunks(self, *, collection_name: str, chunks: List[Dict[str, Any]]) -> None:
        """
        Upsert chunks into Weaviate.
        Each chunk dict should contain:
          - chunk_id (optional)
          - node_id
          - doc_id
          - page
          - type
          - content
          - metadata (dict)
          - embedding (vector) optional
        """
        if not chunks:
            return

        self._ensure_collection(collection_name)

        # Insert via REST batch endpoint to avoid weaviate-client internals.
        import json
        from urllib import request as urlrequest

        base = Config.WEAVIATE_URL.rstrip("/")
        url = f"{base}/v1/batch/objects"

        api_key = getattr(Config, "WEAVIATE_API_KEY", "") or ""
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        objects = []
        for ch in chunks:
            node_id = ch.get("node_id") or ""
            doc_id = ch.get("doc_id") or ""
            page = int(ch.get("page") or 1)
            ctype = ch.get("type") or ""
            content = ch.get("content") or ""
            metadata = ch.get("metadata") or {}
            embedding = ch.get("embedding")

            uid = None
            if node_id and doc_id:
                uid = generate_uuid5(f"{node_id}|{doc_id}|{page}|{ctype}")

            metadata_str = json.dumps(metadata, ensure_ascii=False)

            obj = {
                "class": collection_name,
                "properties": {
                    "node_id": node_id,
                    "doc_id": doc_id,
                    "page": page,
                    "type": ctype,
                    "content": content,
                    "metadata": metadata_str,
                },
            }
            if uid:
                obj["id"] = uid
            if embedding is not None:
                obj["vector"] = embedding

            objects.append(obj)

        payload = {"objects": objects, "batchSize": len(objects)}

        req = urlrequest.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=60) as resp:
            _ = resp.read()
