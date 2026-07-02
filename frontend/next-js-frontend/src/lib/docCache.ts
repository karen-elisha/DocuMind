const DOC_LIST_KEY = "documind_doc_list";

export function saveDocList(docs: string[]): void {
  try { localStorage.setItem(DOC_LIST_KEY, JSON.stringify(docs)); } catch {}
}

export function loadDocList(): string[] {
  try {
    const raw = localStorage.getItem(DOC_LIST_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}
