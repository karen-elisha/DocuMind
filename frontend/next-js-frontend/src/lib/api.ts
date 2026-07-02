const API_URL = "http://localhost:8000";

export async function checkBackendStatus() {
  try {
    const res = await fetch(`${API_URL}/`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function uploadDocument(file: File): Promise<{ doc_id: string; from_cache: boolean; [key: string]: unknown }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_URL}/upload`, { method: "POST", body: formData });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function deleteDocument(filename: string) {
  const res = await fetch(`${API_URL}/document/${encodeURIComponent(filename)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function queryPipeline(query: string, docId?: string, crossDoc: boolean = false) {
  const res = await fetch(`${API_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, doc_id: docId || null, cross_doc: crossDoc }),
  });
  if (!res.ok) {
    const text = await res.text();
    if (res.status === 500 && text.includes("rate_limit")) {
      const wait = text.match(/try again in ([\w.]+)/);
      return {
        answer: `⚠️ Groq rate limit reached (free tier: 100K tokens/day).${wait ? ` Please try again in ${wait[1]}.` : ""}`,
        routed: false, confidence_score: 0, risk_level: "None",
        evidence: { supporting: [], exceptions: [], contradictions: [], risks: [], warnings: [], limitations: [] },
        fact_lock: null, risk_radar: null, documents_used: [],
      };
    }
    throw new Error(text);
  }
  return res.json();
}

export async function queryPipelineStream(
  query: string,
  docId: string | undefined,
  crossDoc: boolean,
  onToken: (token: string) => void,
): Promise<void> {
  const res = await fetch(`${API_URL}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, doc_id: docId || null, cross_doc: crossDoc }),
  });
  if (!res.ok) throw new Error(await res.text());
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const lines = decoder.decode(value).split("\n");
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") return;
      try {
        const parsed = JSON.parse(data);
        if (parsed.error) throw new Error(parsed.error);
        if (parsed.token) onToken(parsed.token);
      } catch (e) { if (e instanceof Error && e.message !== "skip") throw e; }
    }
  }
}

export async function getGraphStats() {
  const res = await fetch(`${API_URL}/graph/stats`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getGraphData() {
  const res = await fetch(`${API_URL}/graph/data`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function resetCollection() {
  const res = await fetch(`${API_URL}/reset`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDocumentInsights(docId: string) {
  const res = await fetch(`${API_URL}/document/${encodeURIComponent(docId)}/insights`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getFigure(docId: string, figureNumber: string) {
  const res = await fetch(`${API_URL}/document/${encodeURIComponent(docId)}/figure/${encodeURIComponent(figureNumber)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getTable(docId: string, tableNumber: string) {
  const res = await fetch(`${API_URL}/document/${encodeURIComponent(docId)}/table/${encodeURIComponent(tableNumber)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listDocuments() {
  const res = await fetch(`${API_URL}/documents`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDemoQuestions(docId: string) {
  const res = await fetch(`${API_URL}/demo/questions?doc_id=${encodeURIComponent(docId)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDocumentMindmap(docId: string) {
  const res = await fetch(`${API_URL}/document/${encodeURIComponent(docId)}/mindmap`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
