"use client";

import { useState, useEffect, useRef } from "react";
import {
  Upload, Trash2, Network, Activity, Send,
  Moon, Sun, ChevronDown, ChevronUp,
  FileText, XCircle, Database, ExternalLink, Map
} from "lucide-react";
import {
  checkBackendStatus, uploadDocument, deleteDocument,
  queryPipeline, getGraphStats, resetCollection,
  getDocumentInsights, getFigure, getTable
} from "@/lib/api";
import dynamic from "next/dynamic";
import DocumentInsights from "@/components/DocumentInsights";
import FigureViewer from "@/components/FigureViewer";
import TableViewer from "@/components/TableViewer";
import MarkdownMessage from "@/components/MarkdownMessage";
import FactLockPanel from "@/components/FactLockPanel";
import DemoModePanel from "@/components/DemoModePanel";
import { buildMindMapChatQuery } from "@/lib/mindmapChat";

const DynamicForceGraph = dynamic(() => import("@/components/ForceGraphView"), {
  ssr: false,
  loading: () => <div className="flex-1 flex items-center justify-center text-slate-400"><Activity className="w-8 h-8 animate-spin" /></div>
});

const DynamicMindMap = dynamic(() => import("@/components/MindMapView"), {
  ssr: false,
  loading: () => <div className="flex-1 flex items-center justify-center text-slate-400"><Activity className="w-8 h-8 animate-spin" /></div>
});

const PdfSectionViewer = dynamic(() => import("@/components/PdfSectionViewer"), { ssr: false });

const RiskRadar = dynamic(() => import("@/components/RiskRadar"), { ssr: false });

type Message = {
  role: "user" | "assistant";
  content: string;
  meta?: any;
};

export default function Workspace() {
  const [isDark, setIsDark] = useState(true);
  const [backendOk, setBackendOk] = useState(false);
  const [docs, setDocs] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadingFilename, setUploadingFilename] = useState<string | null>(null);
  const [showGraph, setShowGraph] = useState(false);
  const [showMindMap, setShowMindMap] = useState(false);
  const [activeNode, setActiveNode] = useState<any>(null);
  const [showPdfUrl, setShowPdfUrl] = useState<string | null>(null);
  const [pdfHighlight, setPdfHighlight] = useState<{
    docId: string;
    page: number;
    bbox?: number[];
    pageHeight?: number;
    searchText?: string;
    label?: string;
  } | null>(null);
  const [stats, setStats] = useState<any>({});

  // Insights
  const [insights, setInsights] = useState<any>(null);
  const [showInsights, setShowInsights] = useState(false);
  const [viewerFigure, setViewerFigure] = useState<any>(null);
  const [viewerTable, setViewerTable] = useState<any>(null);
  const [viewerNearbyText, setViewerNearbyText] = useState("");

  // Settings
  const [targetDoc, setTargetDoc] = useState("");
  const [crossDoc, setCrossDoc] = useState(false);
  const [showEvidence, setShowEvidence] = useState(true);
  const [demoRefresh, setDemoRefresh] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [isDark]);

  useEffect(() => {
    checkBackendStatus().then(setBackendOk);
    getGraphStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadInsights = async (docId: string) => {
    try {
      const result = await getDocumentInsights(docId);
      setInsights(result);
    } catch {
      // insights not available yet
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadingFilename(file.name);
    try {
      const result = await uploadDocument(file);
      const name = file.name;
      if (!docs.includes(name)) {
        setDocs([...docs, name]);
      }
      setTargetDoc(name);
      getGraphStats().then(setStats).catch(() => {});
      // Load insights after successful upload
      if (result.doc_id) {
        await loadInsights(result.doc_id);
        setShowInsights(true);
        setDemoRefresh((k) => k + 1);
      }
    } catch (err) {
      console.error(err);
      alert("Upload failed. Check the backend is running.");
    } finally {
      setUploading(false);
      setUploadingFilename(null);
    }
  };

  const handleDelete = async (filename: string) => {
    try {
      await deleteDocument(filename);
      setDocs(docs.filter(d => d !== filename));
      if (targetDoc === filename) {
        setTargetDoc("");
        setInsights(null);
        setShowInsights(false);
      }
      getGraphStats().then(setStats).catch(() => {});
    } catch (err) {
      console.error(err);
    }
  };

  const handleReset = async () => {
    try {
      await resetCollection();
      setDocs([]);
      setMessages([]);
      setShowGraph(false);
      setShowMindMap(false);
      setStats({});
      setInsights(null);
      setShowInsights(false);
    } catch (err) {
      console.error(err);
    }
  };

  const handleShowFigure = async (figure: any) => {
    setViewerFigure(figure);
    setViewerTable(null);
  };

  const handleShowTable = async (table: any) => {
    setViewerTable(table);
    setViewerFigure(null);
  };

  const submitQuery = async (
    userMsg: string,
    overrideDocId?: string,
    options?: { displayContent?: string },
  ) => {
    if (!userMsg.trim()) return;
    const shown = (options?.displayContent ?? userMsg).trim();
    setMessages(prev => [...prev, { role: "user", content: shown }]);
    setLoading(true);

    try {
      const activeDocId = overrideDocId
        || (targetDoc ? targetDoc.split('.')[0] : undefined);
      const res = await queryPipeline(userMsg.trim(), activeDocId, crossDoc);

      if (res.routed) {
        const msg: Message = {
          role: "assistant",
          content: `**${res.routed_type === "table" ? "Table" : res.routed_type === "chart" ? "Chart" : "Figure"} ${res.routed_number}** — routed directly from document.`,
          meta: {
            routed: true,
            routed_type: res.routed_type,
            routed_number: res.routed_number,
            figure: res.figure,
            table: res.table,
            nearby_text: res.nearby_text,
            confidence_score: res.confidence_score,
            risk_level: res.risk_level,
            documents_used: res.documents_used,
            fact_lock: res.fact_lock,
            risk_radar: res.risk_radar,
          }
        };
        setMessages(prev => [...prev, msg]);

        if (res.figure) {
          setViewerFigure(res.figure);
          setViewerNearbyText(res.nearby_text || "");
        }
        if (res.table) {
          const tbl = { ...res.table, nearbyText: res.nearby_text };
          setViewerTable(tbl);
        }
      } else {
        const msg: Message = {
          role: "assistant",
          content: res.answer || "No answer returned.",
          meta: res,
        };
        setMessages(prev => [...prev, msg]);
      }
    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, { role: "assistant", content: "Query failed. Ensure the FastAPI backend is running on port 8000." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleDemoSelect = (query: string, docId: string) => {
    const existing = docs.find(
      (d) => d.replace(/\.(pdf|docx)$/i, "") === docId,
    );
    const filename = existing || `${docId}.pdf`;
    if (!docs.includes(filename)) {
      setDocs((prev) => (prev.includes(filename) ? prev : [...prev, filename]));
    }
    setTargetDoc(filename);
    loadInsights(docId);
    submitQuery(query, docId);
  };

  const handleMindMapChat = (node: {
    type: string;
    label: string;
    page: number;
    content: string;
    preview?: string;
  }) => {
    const docId = targetDoc ? targetDoc.replace(/\.(pdf|docx)$/i, "") : "";
    if (!docId) return;
    setShowMindMap(false);
    const { display, api } = buildMindMapChatQuery(node);
    submitQuery(api, docId, { displayContent: display });
  };

  const handleMindMapPdf = (node: {
    label: string;
    page: number;
    bbox?: number[];
    page_height?: number;
  }) => {
    const docId = targetDoc ? targetDoc.replace(/\.(pdf|docx)$/i, "") : "";
    if (!docId) return;
    setShowPdfUrl(null);
    setPdfHighlight({
      docId,
      page: node.page,
      bbox: node.bbox,
      pageHeight: node.page_height,
      searchText: node.label,
      label: node.label,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    const userMsg = input.trim();
    setInput("");
    await submitQuery(userMsg);
  };

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-[#0B0F14] text-slate-900 dark:text-slate-100 font-sans transition-colors duration-200">

      {/* Figure Viewer Modal */}
      {viewerFigure && (
        <FigureViewer
          figure={viewerFigure}
          nearbyText={viewerNearbyText}
          onClose={() => { setViewerFigure(null); setViewerNearbyText(""); }}
        />
      )}

      {/* Table Viewer Modal */}
      {viewerTable && (
        <TableViewer
          table={viewerTable}
          onClose={() => setViewerTable(null)}
        />
      )}

      {/* LEFT COLUMN: SOURCES */}
      <div className="w-[320px] flex-shrink-0 border-r border-slate-200 dark:border-slate-800 flex flex-col bg-white dark:bg-[#111827]">
        <div className="p-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div className="font-bold text-lg flex items-center gap-2 tracking-tight">
            <Database className="w-5 h-5 text-emerald-500" />
            <span>Docu<span className="text-emerald-500">Mind</span></span>
          </div>
          <div className={`text-[10px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wider flex items-center gap-1.5 ${backendOk ? 'bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-500 border-emerald-200 dark:border-emerald-500/20' : 'bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-500 border-red-200 dark:border-red-500/20'}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${backendOk ? 'bg-emerald-500' : 'bg-red-500'}`} />
            {backendOk ? 'API Online' : 'API Offline'}
          </div>
        </div>

        <div className="p-5 flex-1 overflow-y-auto">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-semibold text-sm text-slate-800 dark:text-slate-200">Sources</h3>
            <span className="text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">{docs.length} Docs</span>
          </div>

          <label className="border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl p-6 flex flex-col items-center justify-center cursor-pointer hover:border-emerald-500 dark:hover:border-emerald-500 hover:bg-emerald-50 dark:hover:bg-emerald-500/5 transition-all group mb-6">
            <input type="file" className="hidden" accept=".pdf,.docx" onChange={handleUpload} disabled={uploading} />
            {uploading ? (
              <Activity className="w-6 h-6 text-emerald-500 animate-spin mb-2" />
            ) : (
              <Upload className="w-6 h-6 text-slate-400 group-hover:text-emerald-500 mb-2 transition-colors" />
            )}
            <span className="text-sm font-medium text-slate-600 dark:text-slate-400 text-center px-4 truncate w-full">
              {uploading ? `Ingesting ${uploadingFilename}...` : 'Drop files here or click'}
            </span>
          </label>

          {docs.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3">Library</h4>
              {docs.map(doc => (
                <div key={doc} className="group bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700/50 rounded-xl p-3 flex items-center justify-between hover:border-emerald-500/50 dark:hover:border-emerald-500/50 transition-all">
                  <div className="flex items-center gap-3 overflow-hidden flex-1">
                    <FileText className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                    <div className="truncate text-sm font-medium text-slate-700 dark:text-slate-300">{doc}</div>
                  </div>
                  <div className="flex items-center gap-1">
                    {insights && (
                      <button
                        onClick={() => { loadInsights(doc.split('.')[0]); setShowInsights(true); }}
                        className="text-slate-400 hover:text-emerald-500 p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="View document insights"
                      >
                        <FileText className="w-3.5 h-3.5" />
                      </button>
                    )}
                    <button onClick={() => handleDelete(doc)} className="text-slate-400 hover:text-red-500 p-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* CENTER COLUMN: CHAT */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        <div className="h-14 border-b border-slate-200 dark:border-slate-800 flex items-center px-6 justify-between flex-shrink-0 bg-white/80 dark:bg-[#0B0F14]/80 backdrop-blur-md z-10">
          <div className="font-semibold text-sm">Research Notebook</div>
          <div className="flex items-center gap-3">
            {insights && (
              <button
                onClick={() => setShowInsights(!showInsights)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider border transition-colors ${
                  showInsights
                    ? 'bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-500 border-emerald-200 dark:border-emerald-500/20'
                    : 'text-slate-500 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                Insights
              </button>
            )}
            <button onClick={() => setIsDark(!isDark)} className="p-2 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 transition-colors">
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Main content area */}
          <div className={`flex-1 flex flex-col overflow-hidden ${showInsights ? 'border-r border-slate-200 dark:border-slate-800' : ''}`}>
            {showMindMap && targetDoc ? (
              <div className="relative bg-white dark:bg-[#0B0F14] overflow-hidden flex-1">
                <DynamicMindMap
                  docId={targetDoc.replace(/\.(pdf|docx)$/i, "")}
                  onClose={() => setShowMindMap(false)}
                  onChat={handleMindMapChat}
                  onViewPdf={handleMindMapPdf}
                />
              </div>
            ) : showGraph ? (
              <div className="relative bg-white dark:bg-[#0B0F14] overflow-hidden flex-1">
                <DynamicForceGraph onNodeClick={(node) => setActiveNode(node)} />

                {activeNode && (
                  <div className="absolute top-4 left-4 w-80 bg-white/95 dark:bg-[#111827]/95 backdrop-blur-md shadow-xl border border-slate-200 dark:border-slate-800 rounded-2xl p-5 z-20 flex flex-col max-h-[90%] overflow-hidden transition-all">
                    <div className="flex justify-between items-start mb-4 flex-shrink-0">
                      <div>
                        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Node Inspector</div>
                        <div className="flex items-center gap-2">
                          <span className="bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-500 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border border-emerald-200 dark:border-emerald-500/20">
                            {activeNode.type}
                          </span>
                          {activeNode.page && <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Page {activeNode.page}</span>}
                        </div>
                      </div>
                      <button onClick={() => setActiveNode(null)} className="text-slate-400 hover:text-red-500 transition-colors">
                        <XCircle className="w-5 h-5" />
                      </button>
                    </div>

                    <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
                      <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-wrap font-medium">
                        {activeNode.content}
                      </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-800 flex-shrink-0 flex items-center justify-between">
                      <div className="text-[9px] text-slate-400 font-mono break-all bg-slate-50 dark:bg-[#0B0F14] p-2 rounded-lg border border-slate-200 dark:border-slate-800 flex-1 mr-2">
                        ID: {activeNode.id}
                      </div>
                      {activeNode.doc_id && activeNode.page && (
                        <button
                          onClick={() => {
                            const cleanContent = activeNode.content ? activeNode.content.replace(/[\r\n]+/g, ' ').trim() : '';
                            const searchStr = cleanContent.length > 30 ? cleanContent.substring(0, 30) : cleanContent;
                            const searchQuery = searchStr ? `&search="${encodeURIComponent(searchStr)}"` : '';
                            setShowPdfUrl(`http://localhost:8000/document/file/${activeNode.doc_id}#page=${activeNode.page}${searchQuery}`);
                          }}
                          className="bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-500/10 dark:hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-500 px-3 py-2 rounded-lg transition-colors border border-emerald-200 dark:border-emerald-500/20 flex-shrink-0 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider cursor-pointer"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          View in PDF
                        </button>
                      )}
                    </div>
                  </div>
                )}

                <button
                  onClick={() => { setShowGraph(false); setActiveNode(null); setShowPdfUrl(null); }}
                  className="absolute top-4 right-4 bg-white/90 dark:bg-slate-800/90 shadow-lg border border-slate-200 dark:border-slate-700 px-4 py-2 rounded-full text-sm font-semibold flex items-center gap-2 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors z-20 backdrop-blur-sm"
                >
                  <XCircle className="w-4 h-4" /> Close Graph
                </button>
              </div>
            ) : (
              <>
                <div className="flex-1 overflow-y-auto p-6 scroll-smooth">
                  {messages.length === 0 && docs.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
                      <Database className="w-16 h-16 opacity-20" />
                      <div className="text-xl font-semibold text-slate-500">No sources added yet</div>
                      <div className="text-sm">Upload documents to begin querying your knowledge base.</div>
                    </div>
                  ) : messages.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
                      <Activity className="w-16 h-16 opacity-20" />
                      <div className="text-xl font-semibold text-slate-500">Ready to Answer</div>
                      <div className="text-sm">Ask a question below to start researching.</div>
                    </div>
                  ) : (
                    <div className="max-w-4xl mx-auto space-y-6">
                      {messages.map((msg, i) => (
                        <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                          <div className={`max-w-[85%] rounded-2xl p-5 shadow-sm border ${
                            msg.role === 'user'
                              ? 'bg-slate-100 dark:bg-slate-800/80 border-slate-200 dark:border-slate-700 rounded-br-sm'
                              : 'bg-white dark:bg-[#111827] border-slate-200 dark:border-slate-800 rounded-bl-sm shadow-md'
                          }`}>
                            <MarkdownMessage content={msg.content} />
                            {msg.role === 'assistant' && msg.meta && (
                              <EvidencePanel
                                meta={msg.meta}
                                showEvidence={showEvidence}
                                onShowPdf={setShowPdfUrl}
                                onShowFigure={handleShowFigure}
                                onShowTable={handleShowTable}
                                targetDoc={targetDoc}
                              />
                            )}
                          </div>
                        </div>
                      ))}
                      {loading && (
                        <div className="flex justify-start">
                          <div className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 rounded-2xl rounded-bl-sm p-5 flex items-center gap-3 text-slate-500 shadow-md">
                            <Activity className="w-4 h-4 animate-spin text-emerald-500" />
                            <span className="text-sm font-medium animate-pulse">Synthesizing response...</span>
                          </div>
                        </div>
                      )}
                      <div ref={messagesEndRef} />
                    </div>
                  )}
                </div>

                <div className="p-6 bg-slate-50 dark:bg-[#0B0F14] border-t border-slate-200 dark:border-slate-800">
                  <form onSubmit={handleSubmit} className="max-w-4xl mx-auto relative flex items-center">
                    <input
                      type="text"
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      placeholder="Ask your documents anything... (e.g. 'Explain Figure 4' or 'Show Table 1')"
                      className="w-full bg-white dark:bg-[#111827] border border-slate-300 dark:border-slate-700 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-2xl py-4 pl-5 pr-14 outline-none transition-all shadow-sm text-sm"
                    />
                    <button
                      type="submit"
                      disabled={!input.trim() || loading}
                      className="absolute right-2 p-2 bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-300 disabled:dark:bg-slate-700 text-white rounded-xl transition-colors shadow-sm"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                  </form>
                </div>
              </>
            )}
          </div>

          {/* Insights sidebar */}
          {showInsights && insights && (
            <div className="w-[480px] flex-shrink-0 overflow-y-auto bg-white dark:bg-[#111827]">
              <DocumentInsights
                data={insights}
                onClose={() => setShowInsights(false)}
                onShowFigure={handleShowFigure}
                onShowTable={handleShowTable}
              />
            </div>
          )}

          {/* PDF viewer */}
          {(showPdfUrl || pdfHighlight) && (
            <div className="w-1/2 flex flex-col bg-slate-100 dark:bg-[#111827] relative">
              <div className="h-14 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-6 bg-white/80 dark:bg-[#0B0F14]/80 backdrop-blur-md flex-shrink-0 z-10">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Document Viewer</span>
                <button
                  onClick={() => { setShowPdfUrl(null); setPdfHighlight(null); }}
                  className="text-slate-400 hover:text-red-500 transition-colors"
                >
                  <XCircle className="w-5 h-5" />
                </button>
              </div>
              {pdfHighlight ? (
                <PdfSectionViewer highlight={pdfHighlight} />
              ) : (
                <iframe src={showPdfUrl!} className="flex-1 w-full border-none" />
              )}
            </div>
          )}
        </div>
      </div>

      {/* RIGHT COLUMN: STUDIO */}
      <div className="w-[320px] flex-shrink-0 border-l border-slate-200 dark:border-slate-800 flex flex-col bg-white dark:bg-[#111827]">
        <div className="p-5 border-b border-slate-200 dark:border-slate-800">
          <h3 className="font-semibold text-sm">Studio</h3>
        </div>

        <div className="p-5 overflow-y-auto space-y-8 flex-1">
          <div className="space-y-3">
            <button
              onClick={() => { setShowGraph(true); setShowMindMap(false); }}
              className="w-full flex items-center gap-3 p-4 bg-slate-50 dark:bg-[#0B0F14] border border-slate-200 dark:border-slate-800 rounded-xl hover:border-emerald-500 hover:shadow-sm transition-all font-semibold text-sm group"
            >
              <Network className="w-5 h-5 text-slate-400 group-hover:text-emerald-500 transition-colors" />
              Knowledge Graph
            </button>
            {targetDoc && (
              <button
                onClick={() => { setShowMindMap(true); setShowGraph(false); }}
                className="w-full flex items-center gap-3 p-4 bg-slate-50 dark:bg-[#0B0F14] border border-slate-200 dark:border-slate-800 rounded-xl hover:border-amber-500 hover:shadow-sm transition-all font-semibold text-sm group"
              >
                <Map className="w-5 h-5 text-slate-400 group-hover:text-amber-500 transition-colors" />
                Mind Map
              </button>
            )}
            {insights && (
              <button
                onClick={() => setShowInsights(!showInsights)}
                className="w-full flex items-center gap-3 p-4 bg-slate-50 dark:bg-[#0B0F14] border border-slate-200 dark:border-slate-800 rounded-xl hover:border-emerald-500 hover:shadow-sm transition-all font-semibold text-sm group"
              >
                <FileText className="w-5 h-5 text-slate-400 group-hover:text-emerald-500 transition-colors" />
                Document Insights
              </button>
            )}
          </div>

          <div>
            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-4">Graph Metrics</h4>
            <div className="grid grid-cols-2 gap-3">
              <MetricBox label="Total Nodes" value={stats.total_nodes || '—'} />
              <MetricBox label="Positive Edges" value={stats.positive_edges || '—'} />
              <MetricBox label="Total Edges" value={stats.total_edges || '—'} />
              <MetricBox label="Negative Edges" value={stats.negative_edges || '—'} />
            </div>
          </div>

          <hr className="border-slate-200 dark:border-slate-800" />

          <div className="space-y-5">
            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Settings</h4>

            {docs.length > 0 && (
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">Target Document</label>
                <select
                  value={targetDoc}
                  onChange={e => {
                    setTargetDoc(e.target.value);
                    if (e.target.value) {
                      loadInsights(e.target.value.split('.')[0]);
                    }
                  }}
                  className="w-full bg-slate-50 dark:bg-[#0B0F14] border border-slate-200 dark:border-slate-800 rounded-lg p-2.5 text-sm outline-none focus:border-emerald-500 transition-colors"
                >
                  <option value="">All Documents</option>
                  {docs.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
            )}

            <label className="flex items-center justify-between cursor-pointer group">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-emerald-500 transition-colors">Cross-Document QA</span>
              <div className={`w-10 h-5 rounded-full relative transition-colors ${crossDoc ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-700'}`} onClick={() => setCrossDoc(!crossDoc)}>
                <div className={`absolute top-0.5 left-0.5 bg-white w-4 h-4 rounded-full transition-transform ${crossDoc ? 'translate-x-5' : ''}`} />
              </div>
            </label>

            <label className="flex items-center justify-between cursor-pointer group">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300 group-hover:text-emerald-500 transition-colors">Show Evidence</span>
              <div className={`w-10 h-5 rounded-full relative transition-colors ${showEvidence ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-700'}`} onClick={() => setShowEvidence(!showEvidence)}>
                <div className={`absolute top-0.5 left-0.5 bg-white w-4 h-4 rounded-full transition-transform ${showEvidence ? 'translate-x-5' : ''}`} />
              </div>
            </label>
          </div>

          <hr className="border-slate-200 dark:border-slate-800" />

          <DemoModePanel
            targetDoc={targetDoc}
            loading={loading}
            refreshKey={demoRefresh}
            onSelect={handleDemoSelect}
          />

          <hr className="border-slate-200 dark:border-slate-800" />

          <div className="flex gap-3">
            <button onClick={() => setMessages([])} className="flex-1 py-2 text-sm font-semibold rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-slate-600 dark:text-slate-300">
              Clear Chat
            </button>
            <button onClick={handleReset} className="flex-1 py-2 text-sm font-semibold rounded-lg border border-red-200 dark:border-red-900/30 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
              Reset All
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}

function MetricBox({ label, value }: { label: string, value: string | number }) {
  return (
    <div className="bg-slate-50 dark:bg-[#0B0F14] border border-slate-200 dark:border-slate-800 rounded-xl p-3 shadow-sm">
      <div className="text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-1 truncate">{label}</div>
      <div className="text-lg font-bold text-slate-800 dark:text-slate-100">{value}</div>
    </div>
  );
}

function EvidencePanel({
  meta, showEvidence, onShowPdf, onShowFigure, onShowTable, targetDoc
}: {
  meta: any, showEvidence: boolean,
  onShowPdf: (url: string) => void,
  onShowFigure?: (fig: any) => void,
  onShowTable?: (tbl: any) => void,
  targetDoc?: string,
}) {
  // Add onShowTable to the destructured props passed to sub-components
  const [open, setOpen] = useState(false);
  const [miniActiveNode, setMiniActiveNode] = useState<any>(null);

  // Handle routed figure/table responses
  if (meta.routed) {
    return (
      <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700/50 space-y-3">
        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
            meta.routed_type === 'table'
              ? 'bg-amber-100 dark:bg-amber-500/10 text-amber-600 dark:text-amber-500 border-amber-200 dark:border-amber-500/20'
              : 'bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-500 border-emerald-200 dark:border-emerald-500/20'
          }`}>
            {meta.routed_type} {meta.routed_number}
          </span>
          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Direct Match</span>
        </div>
        <div className="flex gap-2">
          {meta.figure && onShowFigure && (
            <button
              onClick={() => onShowFigure(meta.figure)}
              className="px-3 py-1.5 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-lg text-xs font-semibold border border-emerald-200 dark:border-emerald-500/20 hover:bg-emerald-100 transition-colors"
            >
              View Figure
            </button>
          )}
          {meta.table && onShowTable && (
            <button
              onClick={() => onShowTable(meta.table)}
              className="px-3 py-1.5 bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 rounded-lg text-xs font-semibold border border-amber-200 dark:border-amber-500/20 hover:bg-amber-100 transition-colors"
            >
              View Table
            </button>
          )}
        </div>
        <div className="flex items-center gap-3 text-[11px] font-bold uppercase tracking-wider">
          <div className="px-2.5 py-1 rounded-full border text-slate-600 bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700">
            Risk: {meta.risk_level || "None"}
          </div>
          <div className="text-emerald-600 dark:text-emerald-400">
            Confidence: {Math.round((meta.confidence_score || 0) * 100)}%
          </div>
        </div>
      </div>
    );
  }

  const risk = meta.risk_level || "None";
  const conf = Math.round((meta.confidence_score || 0) * 100);
  const ev = meta.evidence || {};

  const supporting = ev.supporting || [];
  const risks = [
    ...(ev.exceptions || []),
    ...(ev.contradictions || []),
    ...(ev.risks || []),
    ...(ev.warnings || []),
    ...(ev.limitations || [])
  ];

  const getRiskColor = (r: string) => {
    switch (r.toLowerCase()) {
      case 'high': return 'text-red-600 bg-red-100 dark:bg-red-500/10 border-red-200 dark:border-red-500/20';
      case 'medium': return 'text-amber-600 bg-amber-100 dark:bg-amber-500/10 border-amber-200 dark:border-amber-500/20';
      case 'low': return 'text-emerald-600 bg-emerald-100 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20';
      default: return 'text-slate-600 bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700';
    }
  };

  const getConfColor = (c: number) => {
    if (c >= 80) return 'bg-emerald-500';
    if (c >= 50) return 'bg-amber-500';
    return 'bg-red-500';
  };

  return (
    <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700/50">

      <FactLockPanel
        factLock={meta.fact_lock}
        onViewPage={(page) => {
          const docId = targetDoc ? targetDoc.replace(/\.(pdf|docx)$/i, "") : meta.documents_used?.[0];
          if (docId) {
            onShowPdf(`http://localhost:8000/document/file/${docId}.pdf#page=${page}`);
          }
        }}
      />

      <RiskRadar data={meta.risk_radar} />

      {/* Figure/Table in evidence - show quick view buttons */}
      {supporting.some((n: any) => n.image_data) && (
        <div className="mb-4 flex flex-wrap gap-2">
          {supporting.filter((n: any) => n.image_data).slice(0, 3).map((node: any, i: number) => (
            <button
              key={i}
              onClick={() => onShowFigure?.(node)}
              className="px-3 py-1.5 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 rounded-lg text-xs font-semibold border border-emerald-200 dark:border-emerald-500/20 hover:bg-emerald-100 transition-colors flex items-center gap-1.5"
            >
              View {node.type || "Figure"}
            </button>
          ))}
        </div>
      )}

      {showEvidence && supporting.length > 0 && !meta.risk_radar?.active && (
        <div className="mb-5">
          <div className="text-[10px] font-bold text-emerald-500 dark:text-emerald-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
            <Network className="w-3.5 h-3.5" />
            Related Subnodes & Child Nodes
          </div>
          <div className="h-[300px] rounded-xl overflow-hidden border border-slate-200 dark:border-slate-700/50 relative bg-white dark:bg-[#0B0F14]">
            <DynamicForceGraph
              graphData={{ nodes: [...supporting, ...risks], edges: ev.edges || [] }}
              onNodeClick={(node) => setMiniActiveNode(node)}
            />
            {miniActiveNode && (
              <div className="absolute top-2 right-2 w-64 bg-white/95 dark:bg-[#111827]/95 backdrop-blur-md shadow-lg border border-slate-200 dark:border-slate-800 rounded-xl p-3 z-20 flex flex-col max-h-[90%] overflow-hidden">
                <div className="flex justify-between items-start mb-2">
                  <span className="bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-500 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border border-emerald-200 dark:border-emerald-500/20">
                    {miniActiveNode.type || 'NODE'}
                  </span>
                  <button onClick={() => setMiniActiveNode(null)} className="text-slate-400 hover:text-red-500">
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto pr-1 text-xs text-slate-700 dark:text-slate-300 leading-relaxed custom-scrollbar mb-3">
                  {miniActiveNode.content}
                </div>
                {miniActiveNode.doc_id && miniActiveNode.page && (
                  <button
                    onClick={() => {
                      const cleanContent = miniActiveNode.content ? miniActiveNode.content.replace(/[\r\n]+/g, ' ').trim() : '';
                      const searchStr = cleanContent.length > 30 ? cleanContent.substring(0, 30) : cleanContent;
                      const searchQuery = searchStr ? `&search="${encodeURIComponent(searchStr)}"` : '';
                      onShowPdf(`http://localhost:8000/document/file/${miniActiveNode.doc_id}#page=${miniActiveNode.page}${searchQuery}`);
                    }}
                    className="w-full bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-500/10 dark:hover:bg-emerald-500/20 text-emerald-600 dark:text-emerald-500 py-1.5 rounded-lg transition-colors border border-emerald-200 dark:border-emerald-500/20 flex items-center justify-center gap-1.5 text-[9px] font-bold uppercase tracking-wider cursor-pointer"
                  >
                    <ExternalLink className="w-3 h-3" />
                    View in PDF
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center gap-4 text-[11px] font-bold uppercase tracking-wider">
        <div className={`px-2.5 py-1 rounded-full border ${getRiskColor(risk)}`}>
          Risk: {risk}
        </div>
        <div className="flex-1 max-w-[150px]">
          <div className="flex justify-between mb-1.5 text-[9px] text-slate-500 tracking-widest">
            <span>Confidence</span>
            <span>{conf}%</span>
          </div>
          <div className="h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-500 ${getConfColor(conf)}`} style={{ width: `${conf}%` }} />
          </div>
        </div>
      </div>

      {showEvidence && (
        <div className="mt-4">
          <button
            onClick={() => setOpen(!open)}
            className="flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors uppercase tracking-wider"
          >
            {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            View Evidence & Citations
          </button>

          {open && (
            <div className="mt-4 space-y-5">
              <div className="grid grid-cols-4 gap-2">
                <MetricBox label="Confidence" value={`${conf}%`} />
                <MetricBox label="Supporting" value={supporting.length} />
                <MetricBox label="Exceptions" value={risks.length} />
                <MetricBox label="Risk Level" value={risk} />
              </div>

              {supporting.length > 4 && (
                <div>
                  <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5">More Supporting Evidence</div>
                  <div className="space-y-2">
                    {supporting.slice(4, 10).map((node: any, i: number) => (
                      <EvCard key={i} node={node} isRisk={false} onShowFigure={onShowFigure} onShowTable={onShowTable} onShowPdf={onShowPdf} />
                    ))}
                  </div>
                </div>
              )}

              {risks.length > 0 && (
                <div>
                  <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5">Exceptions & Risks</div>
                  <div className="space-y-2">
                    {risks.slice(0, 5).map((node: any, i: number) => (
                      <EvCard key={i} node={node} isRisk={true} onShowPdf={onShowPdf} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EvCard({ node, isRisk, onShowFigure, onShowTable, onShowPdf }: {
  node: any, isRisk: boolean,
  onShowFigure?: (fig: any) => void,
  onShowTable?: (tbl: any) => void,
  onShowPdf?: (url: string) => void,
}) {
  const isFigure = ["image", "figure", "chart"].includes((node.type || "").toLowerCase());
  const isTable = (node.type || "").toLowerCase() === "table";
  const hasImageData = node.image_data || node.image_data_base64;

  return (
    <div className={`p-3.5 rounded-xl border bg-white dark:bg-[#111827] shadow-sm transition-all ${isRisk ? 'border-l-4 border-l-red-500 border-slate-200 dark:border-slate-800' : 'border-l-4 border-l-emerald-500 border-slate-200 dark:border-slate-800'}`}>
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        {node.figure_number && (
          <span className="bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-500 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border border-emerald-200 dark:border-emerald-500/20">
            Fig. {node.figure_number}
          </span>
        )}
        {node.table_number && (
          <span className="bg-amber-100 dark:bg-amber-500/10 text-amber-600 dark:text-amber-500 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border border-amber-200 dark:border-amber-500/20">
            Table {node.table_number}
          </span>
        )}
        <span className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border border-slate-200 dark:border-slate-700">
          {node.type || 'NODE'}
        </span>
        {node.page && (
          <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
            p.{node.page}
          </span>
        )}
      </div>

      {/* ── Issue 2: Inline image for figure nodes ── */}
      {isFigure && hasImageData && (
        <div className="mb-3 rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-[#0B0F14]">
          <img
            src={`data:image/jpeg;base64,${node.image_data}`}
            alt={node.caption || `Figure ${node.figure_number}`}
            className="w-full h-48 object-contain cursor-pointer hover:opacity-90 transition-opacity"
            onClick={() => onShowFigure?.(node)}
          />
          {node.vision_summary && (
            <div className="p-2 border-t border-slate-200 dark:border-slate-700">
              <div className="text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-0.5">Vision</div>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 line-clamp-3">{node.vision_summary}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Issue 5: Mini table preview for table nodes ── */}
      {isTable && node.headers && node.headers.length > 0 && (
        <div className="mb-3 overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
          <table className="w-full text-[11px] border-collapse">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/50">
                {node.headers.slice(0, 4).map((h: string, ci: number) => (
                  <th key={ci} className="px-2 py-1.5 text-left font-bold text-slate-500 uppercase tracking-wider border-b border-slate-200 dark:border-slate-700">
                    {h}
                  </th>
                ))}
                {node.headers.length > 4 && <th className="px-2 py-1.5 text-slate-400">+{node.headers.length - 4}</th>}
              </tr>
            </thead>
            <tbody>
              {(node.rows || []).slice(0, 3).map((row: string[], ri: number) => (
                <tr key={ri} className="border-b border-slate-100 dark:border-slate-800/50 last:border-0">
                  {row.slice(0, 4).map((cell: string, ci: number) => (
                    <td key={ci} className="px-2 py-1.5 text-slate-600 dark:text-slate-400 truncate max-w-[100px]">{cell}</td>
                  ))}
                  {row.length > 4 && <td className="px-2 py-1.5 text-slate-400">...</td>}
                </tr>
              ))}
              {node.rows && node.rows.length > 3 && (
                <tr><td colSpan={Math.min(node.headers.length, 4) + (node.headers.length > 4 ? 1 : 0)} className="px-2 py-1.5 text-[10px] text-slate-400 text-center italic">+{node.rows.length - 3} more rows</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed line-clamp-3">
        {node.content}
      </div>

      <div className="mt-2 flex items-center gap-2 flex-wrap">
        {isFigure && hasImageData && onShowFigure && (
          <button onClick={() => onShowFigure(node)}
            className="text-[10px] font-bold text-emerald-500 uppercase tracking-wider hover:underline flex items-center gap-1"
          >
            View Full Image
          </button>
        )}
        {isTable && onShowTable && (
          <button onClick={() => onShowTable(node)}
            className="text-[10px] font-bold text-amber-500 uppercase tracking-wider hover:underline flex items-center gap-1"
          >
            View Full Table
          </button>
        )}
        {node.doc_id && node.page && onShowPdf && (
          <button onClick={() => onShowPdf(node.pdf_url || `http://localhost:8000/document/file/${node.doc_id}.pdf#page=${node.page}`)}
            className="text-[10px] font-bold text-slate-500 uppercase tracking-wider hover:underline flex items-center gap-1"
          >
            View PDF
          </button>
        )}
      </div>
    </div>
  );
}
