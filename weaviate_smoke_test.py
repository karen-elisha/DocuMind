from __future__ import annotations

import json
from urllib import request as urlrequest
from urllib.error import HTTPError

from config import Config


def _rest_headers() -> dict:
    api_key = getattr(Config, "WEAVIATE_API_KEY", "") or ""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _schema_contains_class(class_name: str) -> bool:
    base = Config.WEAVIATE_URL.rstrip("/")
    schema_url = f"{base}/v1/schema"

    req = urlrequest.Request(url=schema_url, method="GET", headers=_rest_headers())
    with urlrequest.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="ignore")

    return f'"class":"{class_name}"' in body or f'"class": "{class_name}"' in body


def _graphql_fetch_by_node_id(class_name: str, node_id: str) -> dict:
    base = Config.WEAVIATE_URL.rstrip("/")
    url = f"{base}/v1/graphql"

    query = f"""
    {{
      Get {{
        {class_name}(where: {{path: ["node_id"], operator: Equal, valueText: "{node_id}"}}) {{
          node_id
          doc_id
          page
          type
          content
          metadata
        }}
      }}
    }}
    """

    payload = {"query": query}
    req = urlrequest.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_rest_headers(),
        method="POST",
    )
    with urlrequest.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    class_name = getattr(Config, "WEAVIATE_COLLECTION", None) or "DocuMindNode"

    test_node_id = "node_test_smoke_once"
    test_doc_id = "doc_test_smoke_once"

    print(f"[SmokeTest] WEAVIATE_URL={Config.WEAVIATE_URL}")
    print(f"[SmokeTest] class={class_name}")

    exists = False
    try:
        exists = _schema_contains_class(class_name)
    except Exception as e:
        print(f"[SmokeTest] schema existence check failed: {e!r}")

    print(f"[SmokeTest] collection exists? {exists}")

    # Insert via v1/batch/objects (create class beforehand handled by wrapper in normal flow;
    # smoke test only inserts. If class doesn't exist, insertion will fail and we’ll see it.)
    base = Config.WEAVIATE_URL.rstrip("/")
    batch_url = f"{base}/v1/batch/objects"

    obj = {
        "class": class_name,
        "properties": {
            "node_id": test_node_id,
            "doc_id": test_doc_id,
            "page": 1,
            "type": "paragraph",
            "content": "SMOKE_TEST inserted by weaviate_smoke_test.py",
            "metadata": json.dumps({"source": "weaviate_smoke_test.py"}, ensure_ascii=False),
        },
    }

    req = urlrequest.Request(
        url=batch_url,
        data=json.dumps({"objects": [obj], "batchSize": 1}).encode("utf-8"),
        headers=_rest_headers(),
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=60) as resp:
            _ = resp.read()
        print("[SmokeTest] insertion request completed")
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"[SmokeTest] insertion failed: HTTP {e.code} body={body[:500]}")
        raise

    # Retrieve it back via GraphQL
    result = _graphql_fetch_by_node_id(class_name, test_node_id)
    hits = (
        result.get("data", {})
        .get("Get", {})
        .get(class_name, [])
    )

    print(f"[SmokeTest] fetch hits: {len(hits)}")
    if hits:
        print("[SmokeTest] fetched object preview:", hits[0])
        print("[SmokeTest] SUCCESS")
    else:
        print("[SmokeTest] No hits found after insertion. Possibly ingestion/schema mismatch.")
        print("[SmokeTest] FAILURE")


if __name__ == "__main__":
    main()
