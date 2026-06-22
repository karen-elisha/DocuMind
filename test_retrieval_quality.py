"""
Retrieval Quality Validation Tests.

Tests run against the FastAPI app via HTTP (server must be running).

Run: python test_retrieval_quality.py
"""

import json, sys, os, time, io, uuid, traceback, urllib.request, urllib.error
from datetime import datetime

API = "http://localhost:8000"

PASS = 0
FAIL = 0
RESULTS = []


def log(msg):
    print(f"  {msg}")


def check(ok, label, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        status = "[PASS]"
    else:
        FAIL += 1
        status = "[FAIL]"
    RESULTS.append({"status": status, "label": label, "detail": detail})
    print(f"  {status}  {label}")
    if detail:
        print(f"         {detail}")


def api_get(path):
    try:
        r = urllib.request.urlopen(f"{API}{path}", timeout=15)
        return json.loads(r.read().decode())
    except Exception as e:
        return {"_error": str(e)}


def api_post(path, data=None, timeout=60):
    try:
        req = urllib.request.Request(
            f"{API}{path}",
            data=json.dumps(data).encode() if data else None,
            headers={"Content-Type": "application/json"} if data else {},
            method="POST"
        )
        r = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        return {"_error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"_error": str(e)}


def upload_pdf(filepath):
    """Upload a PDF file."""
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex[:16]}"
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        file_bytes = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()
    try:
        req = urllib.request.Request(
            f"{API}/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST"
        )
        r = urllib.request.urlopen(req, timeout=120)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:1000]
        return {"_error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"_error": str(e)}


def query_api(query, doc_id, cross_doc=False):
    return api_post("/query", {"query": query, "doc_id": doc_id, "cross_doc": cross_doc}, timeout=120)


def get_insights(doc_id):
    return api_get(f"/document/{doc_id}/insights")


def run_tests():
    global PASS, FAIL, RESULTS
    PASS = 0
    FAIL = 0
    RESULTS = []

    print("=" * 60)
    print("  RETRIEVAL QUALITY VALIDATION")
    print(f"  Started: {datetime.now().isoformat()}")
    print("=" * 60)

    # ── Find test PDF ────────────────────────────────────────────
    uploads_dir = os.path.join(os.getcwd(), "data", "uploads")
    test_pdf = os.path.join(uploads_dir, "embedded-images-tables.pdf")
    if not os.path.exists(test_pdf):
        print(f"\n  Test PDF not found at: {test_pdf}")
        return

    # ── Upload ───────────────────────────────────────────────────
    print(f"\n[UPLOAD] {test_pdf}")
    t0 = time.time()
    upload_res = upload_pdf(test_pdf)
    elapsed = time.time() - t0
    print(f"  Upload took {elapsed:.1f}s")
    check("_error" not in upload_res, "Upload PDF", str(upload_res.get("_error", "")))
    if "_error" in upload_res:
        print("  Aborting tests.")
        return

    doc_id = upload_res.get("doc_id") or os.path.splitext(os.path.basename(test_pdf))[0]
    log(f"  doc_id = {doc_id}")

    # ── Wait for insights ────────────────────────────────────────
    time.sleep(2)
    insights = get_insights(doc_id)
    has_insights = "_error" not in insights
    check(has_insights, "Document insights available", str(insights.get("_error", "")))
    if has_insights:
        log(f"  Pages: {insights.get('stats', {}).get('pages')}")
        log(f"  Images: {insights.get('stats', {}).get('images')}")
        log(f"  Tables: {insights.get('stats', {}).get('tables')}")
        log(f"  Headings: {insights.get('stats', {}).get('headings')}")

    # ── Also upload the "Attention is all you need" PDF ───────────
    transformer_pdf = os.path.join(os.getcwd(), "data", "uploads", "NIPS-2017-attention-is-all-you-need-Paper (1).pdf")
    transformer_doc_id = None
    if os.path.exists(transformer_pdf):
        print(f"\n[UPLOAD] Transformer paper")
        t0 = time.time()
        up2 = upload_pdf(transformer_pdf)
        log(f"  Upload took {time.time()-t0:.1f}s")
        if "_error" not in up2:
            transformer_doc_id = up2.get("doc_id") or "NIPS-2017-attention-is-all-you-need-Paper_1_"
            log(f"  doc_id = {transformer_doc_id}")
            time.sleep(2)
            ins2 = get_insights(transformer_doc_id)
            if "_error" not in ins2:
                log(f"  Pages: {ins2.get('stats', {}).get('pages')}")
                log(f"  Images: {ins2.get('stats', {}).get('images')}")
                log(f"  Tables: {ins2.get('stats', {}).get('tables')}")
        else:
            log(f"  Upload failed: {up2.get('_error', '')[:100]}")
    else:
        log(f"  Transformer PDF not found at: {transformer_pdf}")

    # ── Test 1: "Explain the abstract" ───────────────────────────
    print("\n[TEST 1] Explain the abstract")
    print("  Expected: Abstract section content")
    r1 = query_api("Explain the abstract", transformer_doc_id or doc_id)
    if "_error" not in r1:
        evidence = r1.get("evidence", {})
        supporting = evidence.get("supporting", [])
        contents = [str(n.get("content", "")).strip().lower() for n in supporting if n.get("content")]
        has_abstract = any("abstract" in c[:80] for c in contents)
        check(has_abstract, "Top-5 evidence contains abstract section")
        log(f"  Supporting nodes: {len(supporting)}")
        log(f"  Confidence: {r1.get('confidence_score', 'N/A')}")
        if supporting:
            log(f"  Top content preview: {str(supporting[0].get('content',''))[:100]}")
    else:
        check(False, "Query succeeded", str(r1.get("_error", "")))

    # ── Test 2: "What is the Transformer?" ──────────────────────
    print("\n[TEST 2] What is the Transformer?")
    print("  Expected: Introduction + Abstract")
    r2 = query_api("What is the Transformer?", transformer_doc_id or doc_id)
    if "_error" not in r2:
        evidence = r2.get("evidence", {})
        supporting = evidence.get("supporting", [])
        contents = [str(n.get("content", "")).strip().lower() for n in supporting if n.get("content")]
        has_transformer = any("transformer" in c[:100] for c in contents)
        check(has_transformer, "Top-5 evidence contains Transformer content")
        log(f"  Supporting nodes: {len(supporting)}")
        log(f"  Confidence: {r2.get('confidence_score', 'N/A')}")
        if supporting:
            log(f"  Top content preview: {str(supporting[0].get('content',''))[:100]}")
    else:
        check(False, "Query succeeded", str(r2.get("_error", "")))

    # ── Test 3: "Explain Table 1" ─────────────────────────────────
    print("\n[TEST 3] Explain Table 1")
    print("  Expected: Table 1 evidence")
    r3 = query_api("Explain Table 1", transformer_doc_id or doc_id)
    if "_error" not in r3:
        if r3.get("routed"):
            # Routed table path
            tbl_data = r3.get("table")
            has_headers = bool(tbl_data and tbl_data.get("headers"))
            has_rows = bool(tbl_data and tbl_data.get("rows"))
            check(has_headers, "Routed table includes headers")
            check(has_rows, "Routed table includes rows")
            log(f"  Routed: table #{r3.get('routed_number')}")
            if tbl_data:
                log(f"  Headers: {tbl_data.get('headers', [])[:3]}")
        else:
            evidence = r3.get("evidence", {})
            supporting = evidence.get("supporting", [])
            has_tbl = any(n.get("table_number") == "1" or n.get("headers") for n in supporting)
            check(has_tbl, "Non-routed table evidence has table data")
            log(f"  Supporting: {len(supporting)} nodes")
    else:
        check(False, "Table query succeeded", str(r3.get("_error", "")))

    # ── Test 4: "What are the conclusions?" ──────────────────────
    print("\n[TEST 4] What are the conclusions?")
    print("  Expected: Conclusion section")
    r4 = query_api("What are the conclusions?", transformer_doc_id or doc_id)
    if "_error" not in r4:
        evidence = r4.get("evidence", {})
        supporting = evidence.get("supporting", [])
        contents = [str(n.get("content", "")).strip().lower() for n in supporting if n.get("content")]
        has_conclusion = any("conclusion" in c[:80] for c in contents)
        check(has_conclusion, "Top-5 evidence contains conclusion section")
        log(f"  Supporting nodes: {len(supporting)}")
        log(f"  Confidence: {r4.get('confidence_score', 'N/A')}")
        if supporting:
            log(f"  Top content preview: {str(supporting[0].get('content',''))[:100]}")
    else:
        check(False, "Query succeeded", str(r4.get("_error", "")))

    # ── Test 5: "Training data used?" ────────────────────────────
    print("\n[TEST 5] Training data used?")
    print("  Expected: Training Data section")
    r5 = query_api("Training data used?", transformer_doc_id or doc_id)
    if "_error" not in r5:
        evidence = r5.get("evidence", {})
        supporting = evidence.get("supporting", [])
        contents = [str(n.get("content", "")).strip().lower() for n in supporting if n.get("content")]
        has_training = any("training" in c[:100] and ("data" in c or "dataset" in c or "wmt" in c) for c in contents)
        check(has_training, "Top-5 evidence contains training data section")
        log(f"  Supporting nodes: {len(supporting)}")
        log(f"  Confidence: {r5.get('confidence_score', 'N/A')}")
        if supporting:
            log(f"  Top content preview: {str(supporting[0].get('content',''))[:100]}")
    else:
        check(False, "Query succeeded", str(r5.get("_error", "")))

    # ── Test 6: Figure query (Issue 2+3) ──────────────────────────
    print("\n[TEST 6] Figure query: What does Figure 1 show?")
    r6 = query_api("What does Figure 1 show?", doc_id)
    if "_error" not in r6:
        evidence = r6.get("evidence", {})
        supporting = evidence.get("supporting", [])
        has_image_evidence = any(n.get("image_data") for n in supporting)
        has_fig_caption = any(n.get("caption") and n.get("figure_number") for n in supporting)
        check(has_image_evidence, "Figure evidence includes image_data")
        check(has_fig_caption, "Figure evidence includes caption + figure_number")
        log(f"  Supporting: {len(supporting)} nodes")
    else:
        check(False, "Figure query succeeded", str(r6.get("_error", "")))

    # ── Test 7: Table query (Issue 5+6) ────────────────────────────
    print("\n[TEST 7] Table query: Show Table 1")
    r7 = query_api("Show Table 1", doc_id)
    if "_error" not in r7:
        if r7.get("routed"):
            tbl_data = r7.get("table")
            has_headers = bool(tbl_data and tbl_data.get("headers"))
            has_rows = bool(tbl_data and tbl_data.get("rows"))
            check(has_headers, "Routed table has headers")
            check(has_rows, "Routed table has rows")
        else:
            evidence = r7.get("evidence", {})
            supporting = evidence.get("supporting", [])
            has_tbl_evidence = any(n.get("headers") for n in supporting)
            check(has_tbl_evidence, "Table evidence includes structured headers")
        log(f"  Routed: {r7.get('routed')}")
    else:
        check(False, "Table query succeeded", str(r7.get("_error", "")))

    # ── Test 8: Confidence not hardcoded ──────────────────────────
    print("\n[TEST 8] Confidence score quality")
    r8 = query_api("what is the main topic of this document?", doc_id)
    if "_error" not in r8:
        conf = r8.get("confidence_score", 1.0)
        check(conf != 1.0, f"Confidence is not 100% (got {conf:.2%})")
        check(0.05 <= conf <= 0.98, f"Confidence in valid range (got {conf:.2%})")
        log(f"  Confidence: {conf:.2%}")
    else:
        check(False, "Confidence query", str(r8.get("_error", "")))

    # ── Test 9: Image query returns image nodes ──────────────────
    print("\n[TEST 9] Image query: explain polarization figure")
    r9 = query_api("explain the figure about polarization", doc_id)
    if "_error" not in r9:
        evidence = r9.get("evidence", {})
        supporting = evidence.get("supporting", [])
        img_nodes = [n for n in supporting if str(n.get("type", "")).lower() in ("image", "figure", "chart")]
        check(len(img_nodes) > 0, f"Image query returns image nodes ({len(img_nodes)})")
        log(f"  Image nodes: {len(img_nodes)}")
    else:
        check(False, "Image query", str(r9.get("_error", "")))

    # ── Final report ──────────────────────────────────────────────
    total = PASS + FAIL
    print("\n" + "=" * 60)
    print(f"  RESULTS: {PASS}/{total} passed, {FAIL}/{total} failed")
    print("=" * 60)
    for r in RESULTS:
        print(f"  {r['status']}  {r['label']}")
    print("=" * 60)

    return FAIL == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
