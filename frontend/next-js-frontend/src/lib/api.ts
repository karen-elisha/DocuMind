const API_URL = "http://localhost:8000";

export async function checkBackendStatus() {
  try {
    const res = await fetch(`${API_URL}/`);
    return res.ok;
  } catch {
    return false;
  }
}

export async function uploadDocument(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function deleteDocument(filename: string) {
  const res = await fetch(`${API_URL}/document/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function queryPipeline(query: string, docId?: string, crossDoc: boolean = false) {
  const res = await fetch(`${API_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      doc_id: docId || null,
      cross_doc: crossDoc,
    }),
  });

  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function getGraphStats() {
  const res = await fetch(`${API_URL}/graph/stats`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function getGraphData() {
  const res = await fetch(`${API_URL}/graph/data`);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}

export async function resetCollection() {
  const res = await fetch(`${API_URL}/reset`, { method: "POST" });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
}
