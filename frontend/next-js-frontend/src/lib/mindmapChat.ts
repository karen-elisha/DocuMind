/** Build a short chat question from a mind-map node (no content dump). */

type MindMapChatNode = {
  type: string;
  label: string;
  preview?: string;
  content?: string;
  page: number;
};

function truncate(text: string, max: number): string {
  const t = text.replace(/\s+/g, " ").trim();
  if (t.length <= max) return t;
  return t.slice(0, max - 1).trimEnd() + "…";
}

function isGenericLabel(label: string): boolean {
  const lower = label.toLowerCase().trim();
  return (
    !lower
    || lower === "section content"
    || lower === "document"
    || lower.length < 4
  );
}

function subjectFromNode(node: MindMapChatNode): string {
  const label = node.label.trim();
  if (!isGenericLabel(label)) return truncate(label, 100);
  const fromPreview = (node.preview || node.content || "").trim();
  if (!fromPreview) return `page ${node.page}`;
  const firstLine = fromPreview.split(/\n/)[0] || fromPreview;
  return truncate(firstLine, 90);
}

export function buildMindMapChatQuery(node: MindMapChatNode): {
  display: string;
  api: string;
} {
  const subject = subjectFromNode(node);
  const page = node.page;

  switch (node.type) {
    case "document":
      return {
        display: "What is this document about?",
        api: `Give a clear overview of "${subject}". What are the main topics and key takeaways?`,
      };

    case "heading":
      return {
        display: `What does "${subject}" cover?`,
        api: `Explain the section "${subject}" (page ${page}). Summarize the key points in plain language.`,
      };

    case "table":
      return {
        display: `What does the table "${subject}" show?`,
        api: `Explain the table "${subject}" on page ${page}. What are the important figures or comparisons?`,
      };

    case "figure":
      return {
        display: `What is shown in ${subject}?`,
        api: `Describe ${subject} on page ${page} and why it matters in this document.`,
      };

    case "content":
    default:
      if (isGenericLabel(node.label)) {
        return {
          display: `Can you explain ${truncate(subject, 72)}?`,
          api: `Summarize the main ideas about ${subject} (page ${page}). Be concise and avoid quoting long passages.`,
        };
      }
      return {
        display: `What does "${subject}" explain?`,
        api: `Summarize and explain "${subject}" on page ${page}. Focus on the gist, not verbatim text.`,
      };
  }
}
