'use client'

import { useState, useEffect } from 'react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';

// ============================================================================
// Type Interfaces
// ============================================================================
interface FactorDetail { mentioned: boolean; polarity: number | null; evidence_strength: 'LOW' | 'MEDIUM' | 'HIGH' | null; confidence: number | null; evidence: string[]; reason: string; }
interface ParsedData { target: { type: string; name: string | null }; explicit_trust: { present: boolean; polarity: string | null; evidence: string[] }; factors: Record<string, FactorDetail>; }
type Note = { id: string; content: string; llm_parsed_data?: ParsedData; human_parsed_data?: ParsedData; verification_status: 'raw' | 'llm_annotated' | 'human_verified'; created_at: string; };

interface DashboardData {
  dataset_summary: { total_reviews: number; llm_annotated_reviews: number; human_verified_reviews: number; verification_rate: number; };
  analysis_metadata: { analysis_basis: string; ai_only_contribution_count: number; human_verified_contribution_count: number; total_reviews_included: number; weight_scheme: string; };
  factor_scores: Record<string, { score: number | null; mention_count: number; mention_rate: number }>;
  factor_statistics: Record<string, { positive_rate: number; neutral_mixed_rate: number; negative_rate: number; }>;
  baseline: { status: string; score: number | null; missing_factors: string[]; };
  adjusted: { status: string; score: number | null; missing_factors: string[]; effective_weights: Record<string, number>; contributions: Record<string, number>; };
  comparison: { signed_difference: number | null; absolute_difference: number | null; };
}

// ============================================================================
// Shared Components
// ============================================================================
const MetricCard = ({ title, value }: { title: string, value: string | number }) => (
  <div className="bg-white p-5 rounded-lg border border-neutral-200">
    <span className="block text-neutral-500 text-xs mb-1">{title}</span>
    <span className="text-2xl font-semibold">{value}</span>
  </div>
);

// ============================================================================
// Component: Evidence Explorer
// ============================================================================
const EvidenceExplorer = ({ factor, analysisBasis }: { factor: string, analysisBasis: string }) => {
  const [evidence, setEvidence] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE_URL}/analytics/evidence?factor=${factor}&analysis_basis=${analysisBasis}&page=${page}`)
      .then(res => res.json()).then(data => { if (data.success) { setEvidence(data.data); setTotalPages(data.pagination.total_pages); }})
      .finally(() => setLoading(false));
  }, [factor, analysisBasis, page]);

  // 改进的高亮函数：支持多段文本高亮，并根据极性(polarity)改变颜色
  const highlight = (text: string, spans: string[], polarity: number | null) => {
    if (!spans || spans.length === 0) return <p className="text-sm text-neutral-600">{text}</p>;
    
    // 根据当前 Factor 的情感极性选择高亮颜色
    const highlightColor = polarity === 1 ? 'bg-emerald-200 text-emerald-900' : 
                           polarity === -1 ? 'bg-rose-200 text-rose-900' : 
                           'bg-neutral-200 text-neutral-900'; // Mixed / Neutral 使用灰色

    const validSpans = spans.filter(s => s.trim().length >= 4);
    if (validSpans.length === 0) return <p className="text-sm text-neutral-600">{text}</p>;

    // 构建正则表达式以匹配所有的 evidence span
    const escapedSpans = validSpans.map(s => s.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const regex = new RegExp(`(${escapedSpans.join('|')})`, 'gi');
    const parts = text.split(regex);

    return (
      <p className="text-sm text-neutral-600 leading-relaxed">
        {parts.map((part, i) => 
          validSpans.some(vs => part.toLowerCase() === vs.toLowerCase()) ? 
            <mark key={i} className={`${highlightColor} px-1 rounded`}>{part}</mark> : 
            part
        )}
      </p>
    );
  };

  if (loading) return <div className="p-8 text-center text-xs text-neutral-400">Loading provenance data...</div>;
  if (evidence.length === 0) return <div className="p-8 text-center text-xs text-neutral-400">No records found.</div>;

  return (
    <div className="p-6 bg-neutral-50/50 border-t border-neutral-200 animate-in fade-in duration-300">
      <div className="flex justify-between items-center mb-6">
        <h3 className="font-medium text-neutral-900">Evidence Explorer: <span className="font-mono">{factor}</span></h3>
        <span className="text-xs text-neutral-500 bg-white border border-neutral-200 px-2 py-1 rounded">Basis: {analysisBasis.toUpperCase()}</span>
      </div>
      <div className="space-y-6">
        {evidence.map(r => (
          <div key={r.id} className="border border-neutral-200 rounded-lg bg-white overflow-hidden shadow-sm">
            <div className="bg-neutral-50 px-4 py-2 border-b border-neutral-200 flex justify-between items-center">
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-neutral-500">ID: {r.id.slice(-8)}</span>
                
                {/* 新增：仅针对当前所选 Factor 的明确情感标签 */}
                {r.factor_data.polarity === 1 && <span className="text-[10px] font-bold px-2 py-0.5 bg-emerald-100 text-emerald-700 border border-emerald-200 rounded">POSITIVE</span>}
                {r.factor_data.polarity === -1 && <span className="text-[10px] font-bold px-2 py-0.5 bg-rose-100 text-rose-700 border border-rose-200 rounded">NEGATIVE</span>}
                {r.factor_data.polarity === 0 && <span className="text-[10px] font-bold px-2 py-0.5 bg-neutral-200 text-neutral-700 border border-neutral-300 rounded">NEUTRAL / MIXED</span>}
              </div>
              <span className="text-[10px] font-bold px-2 py-1 bg-white border border-neutral-200 text-neutral-500 rounded shadow-sm">{r.contributed_as}</span>
            </div>
            
            {/* 传入 polarity 以动态渲染对应颜色的多段高亮 */}
            <div className="p-4 bg-white">{highlight(r.review_text, r.factor_data.evidence || [], r.factor_data.polarity)}</div>
          </div>
        ))}
      </div>
      {totalPages > 1 && (
        <div className="flex justify-center gap-4 mt-6">
          <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="px-3 py-1 bg-white border border-neutral-200 rounded text-xs">Prev</button>
          <span className="text-xs text-neutral-500">Page {page} of {totalPages}</span>
          <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)} className="px-3 py-1 bg-white border border-neutral-200 rounded text-xs">Next</button>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Main App Component
// ============================================================================
export default function Home() {
  const initialWeights = { F1_functional_value: 0.2, F2_transaction_safety: 0.2, F3_integrity: 0.2, F4_reputation: 0.2, F5_interaction: 0.2 };
  
  // View State
  const [viewTab, setViewTab] = useState<'explorer' | 'dashboard'>('explorer');
  const [analysisBasis, setAnalysisBasis] = useState<'hybrid' | 'human_verified' | 'ai_original'>('hybrid');
  
  // Dashboard State
  const [customWeights, setCustomWeights] = useState(initialWeights);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [isCalc, setIsCalc] = useState(true);
  const [selectedFactor, setSelectedFactor] = useState<string | null>(null);

  // Explorer State
  const [notes, setNotes] = useState<Note[]>([]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState({ msg: 'System Ready', type: 'info' });
  const [loadingType, setLoadingType] = useState<'single' | 'batch' | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<ParsedData | null>(null);
  
  // Controller for aborting requests
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  // Load Dashboard Data (Debounced)
  useEffect(() => {
    if (viewTab !== 'dashboard') return;
    const c = new AbortController();
    setIsCalc(true);
    const t = setTimeout(() => {
      fetch(`${API_BASE_URL}/analytics/dashboard/unified`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ analysis_basis: analysisBasis, custom_weights: customWeights }), 
        signal: c.signal 
      })
      .then(res => res.ok ? res.json() : null)
      .then(d => { if (d?.success && !c.signal.aborted) { setDashboard(d); setIsCalc(false); }})
      .catch(() => { if (!c.signal.aborted) setIsCalc(false); });
    }, 250);
    return () => { clearTimeout(t); c.abort(); };
  }, [analysisBasis, customWeights, viewTab]);

  // Load Explorer Data
  useEffect(() => { 
    if (viewTab === 'explorer') loadNotes(); 
  }, [viewTab]);

  const loadNotes = async () => fetch(`${API_BASE_URL}/notes`).then(r => r.json()).then(d => setNotes(d.data || []));
  
  // Persistent status display function
  const showStatus = (msg: string) => { setStatus({ msg, type: 'info' }); };

  // ============================================================================
  // Cancel and Submit Logic
  // ============================================================================
  const handleCancel = () => {
    if (abortController) {
      abortController.abort(); // Trigger abort signal
    }
  };

  const submitAction = async (isBatch: boolean) => {
    if (!input.trim()) return showStatus('Enter text first');
    const lines = isBatch ? input.split(/\n+/).filter(l => l.trim().length > 0) : [input];
    
    setLoadingType(isBatch ? 'batch' : 'single');
    
    // Initialize AbortController
    const controller = new AbortController();
    setAbortController(controller);
    
    let isCancelled = false;

    for (let i = 0; i < lines.length; i++) {
       if (isBatch) showStatus(`Processing record ${i + 1} of ${lines.length}...`);
       
       try {
         const res = await fetch(`${API_BASE_URL}/notes`, { 
           method: 'POST', 
           headers: { 'Content-Type': 'application/json' }, 
           body: JSON.stringify({ content: lines[i], action: 'agent' }),
           signal: controller.signal // Pass abort signal to fetch
         });

         // 1. On success, immediately fetch the latest list to render
         if (res.ok) {
           await loadNotes();
         }
         
         // 2. If batch processing, force a 2-second delay before the next request (anti-rate-limiting)
         if (isBatch && i < lines.length - 1) {
           await new Promise(resolve => setTimeout(resolve, 300));
         }

       } catch (error: any) {
         if (error.name === 'AbortError') {
           isCancelled = true;
           break; // User cancelled, break the loop
         }
         console.error('Request failed:', error);
       }
    }
    
    setLoadingType(null); 
    setAbortController(null);
    
    if (isCancelled) {
      showStatus('Process cancelled by user.');
      loadNotes(); // Refresh on cancel to ensure partially completed data is visible
    } else {
      setInput(''); 
      showStatus(isBatch ? 'Batch complete!' : 'Done');
    }
  };

  const deleteNote = async (id: string) => { if (confirm('Delete this record?')) { await fetch(`${API_BASE_URL}/notes/${id}`, { method: 'DELETE' }); loadNotes(); }};

  const saveVerification = async (id: string) => {
    await fetch(`${API_BASE_URL}/notes/${id}/verify`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ human_data: editForm }) });
    setEditingId(null); loadNotes(); 
  };

  const toggleMention = (k: string) => { setEditForm(prev => { if (!prev) return prev; const m = !prev.factors[k].mentioned; return { ...prev, factors: { ...prev.factors, [k]: { ...prev.factors[k], mentioned: m, polarity: m ? 0 : null } } }; }); };
  const setPolarity = (k: string, v: number) => { setEditForm(prev => { if (!prev) return prev; return { ...prev, factors: { ...prev.factors, [k]: { ...prev.factors[k], mentioned: true, polarity: Math.max(-1, Math.min(1, v)) } } }; }); };

  return (
    <main className="min-h-screen bg-[#FAFAFA] text-neutral-900 font-sans selection:bg-neutral-200 p-6 pt-16 pb-20">
      <div className="max-w-6xl mx-auto space-y-10">
        
        {/* Header Navigation */}
        <header className="flex flex-col md:flex-row justify-between md:items-end border-b border-neutral-200 pb-6 gap-4">
          <div><h1 className="text-3xl font-semibold mb-1">Trust Analytics</h1><p className="text-sm text-neutral-500">Research Engine & Deterministic Aggregation</p></div>
          <div className="flex bg-neutral-100 p-1 rounded-md border">
            {['explorer', 'dashboard'].map(t => (
              <button key={t} onClick={() => setViewTab(t as any)} className={`px-4 py-1.5 text-sm font-medium rounded-sm transition-colors ${viewTab === t ? 'bg-white shadow-sm' : 'text-neutral-500 hover:text-neutral-700'}`}>
                {t === 'explorer' ? 'Dataset Explorer' : 'Research Dashboard'}
              </button>
            ))}
          </div>
        </header>

        {viewTab === 'dashboard' ? ( dashboard ? (
          // ============================================================================
          // DASHBOARD VIEW
          // ============================================================================
          <div className={`space-y-10 transition-opacity ${isCalc ? 'opacity-60' : 'opacity-100'}`}>
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-medium">1. Research Overview</h2>
              <div className="flex items-center gap-3">
                <span className="text-xs text-neutral-500">Analysis Basis:</span>
                <div className="flex bg-neutral-100 p-1 rounded-md border">
                  {[ {k: 'ai_original', v: 'AI Original'}, {k: 'human_verified', v: 'Human Verified'}, {k: 'hybrid', v: 'Hybrid'} ].map(b => (
                    <button key={b.k} onClick={() => setAnalysisBasis(b.k as any)} className={`px-3 py-1 text-xs font-medium rounded-sm ${analysisBasis === b.k ? 'bg-white shadow-sm' : 'text-neutral-500'}`}>{b.v}</button>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard title="Total Reviews" value={dashboard.dataset_summary.total_reviews} />
              <MetricCard title="AI Annotated" value={dashboard.dataset_summary.llm_annotated_reviews} />
              <MetricCard title="Human Verified" value={dashboard.dataset_summary.human_verified_reviews} />
              <MetricCard title="Verification Rate" value={`${(dashboard.dataset_summary.verification_rate * 100).toFixed(1)}%`} />
            </div>

            <div className="space-y-4">
              <h2 className="text-lg font-medium">2-5. Factor-Level Sentiment & Coverage</h2>
              <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
                
                {/* Updated Header Row - cleaner and reflects the new layout */}
                <div className="hidden md:grid grid-cols-1 md:grid-cols-12 gap-6 px-4 py-3 border-b border-neutral-100 bg-white text-[10px] font-bold tracking-wider text-neutral-400 uppercase">
                  <div className="md:col-span-4 flex items-center">Research Dimension</div>
                  <div className="md:col-span-2 flex items-center">Avg Score</div>
                  <div className="md:col-span-4 flex items-center">Sentiment Distribution (Count)</div>
                  <div className="md:col-span-2 flex items-center justify-end">Total Mentions</div>
                </div>

                <div className="divide-y divide-neutral-100">
                  {Object.keys(dashboard.factor_scores).map((fk) => {
                    const d = dashboard.factor_scores[fk], stats = dashboard.factor_statistics[fk];
                    
                    // Explicitly handle "No Data" rows
                    if (d.mention_count === 0 || d.score === null) {
                      return (
                        <div key={fk} className="grid grid-cols-1 md:grid-cols-12 gap-6 p-4 bg-neutral-50/50">
                          <div className="md:col-span-4 flex items-center"><span className="font-mono text-xs font-medium text-neutral-800 opacity-60">{fk.replace(/_/g, ' ')}</span></div>
                          <div className="md:col-span-8 flex items-center">
                            <span className="text-xs italic text-neutral-400">No data available in current subset</span>
                          </div>
                        </div>
                      );
                    }

                    // Calculate exact mention counts for each sentiment polarity
                    const posCount = Math.round(stats.positive_rate * d.mention_count);
                    const neuCount = Math.round(stats.neutral_mixed_rate * d.mention_count);
                    const negCount = Math.round(stats.negative_rate * d.mention_count);

                    return (
                      <div key={fk} onClick={() => setSelectedFactor(selectedFactor === fk ? null : fk)} className="grid grid-cols-1 md:grid-cols-12 gap-6 p-4 cursor-pointer hover:bg-neutral-50 transition-colors">
                        <div className="md:col-span-4 flex items-center"><span className="font-mono text-xs font-medium text-neutral-800">{fk.replace(/_/g, ' ')}</span></div>
                        
                        <div className="md:col-span-2 flex items-center">
                           <span className="font-mono text-sm font-semibold text-neutral-900">{d.score?.toFixed(2)}</span>
                        </div>
                        
                        {/* Unified Sentiment Distribution Bar with Counts */}
                        <div className="md:col-span-4 flex items-center">
                           <div className="w-full h-7 flex rounded overflow-hidden bg-neutral-100 font-mono text-[11px] font-semibold text-white shadow-inner">
                              {posCount > 0 && (
                                <div className="h-full bg-emerald-500 flex items-center justify-center transition-all" style={{ width: `${stats.positive_rate * 100}%` }}>
                                  {stats.positive_rate > 0.08 ? posCount : ''}
                                </div>
                              )}
                              {neuCount > 0 && (
                                <div className="h-full bg-neutral-200 flex items-center justify-center text-neutral-500 transition-all" style={{ width: `${stats.neutral_mixed_rate * 100}%` }}>
                                  {stats.neutral_mixed_rate > 0.08 ? neuCount : ''}
                                </div>
                              )}
                              {negCount > 0 && (
                                <div className="h-full bg-rose-500 flex items-center justify-center transition-all" style={{ width: `${stats.negative_rate * 100}%` }}>
                                  {stats.negative_rate > 0.08 ? negCount : ''}
                                </div>
                              )}
                           </div>
                        </div>

                        <div className="md:col-span-2 flex items-center justify-end">
                           <span className="text-xs font-mono text-neutral-500">{d.mention_count} mentions</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
                {selectedFactor && <EvidenceExplorer factor={selectedFactor} analysisBasis={analysisBasis} />}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
               <div className="md:col-span-1 bg-white border border-neutral-200 rounded-lg p-5">
                 <div className="flex justify-between items-center mb-6"><h3 className="font-medium text-sm">6. Controls</h3><button onClick={() => setCustomWeights(initialWeights)} className="text-[10px] uppercase font-bold text-neutral-500 hover:text-neutral-900 transition-colors">Reset</button></div>
                 <div className="space-y-5">
                   {Object.keys(initialWeights).map(fk => {
                     const effectiveNormalized = dashboard.adjusted.effective_weights?.[fk];
                     return (
                       <div key={fk}>
                         <div className="flex justify-between items-end text-xs mb-2">
                           <span className="font-mono text-neutral-700">{fk.split('_')[0]} Raw: {customWeights[fk as keyof typeof customWeights].toFixed(2)}</span>
                           <div className="text-right">
                             <span className="block text-neutral-900 font-mono text-xs font-medium">
                                {effectiveNormalized !== undefined ? `Effective: ${(effectiveNormalized * 100).toFixed(1)}%` : 'Excluded'}
                             </span>
                           </div>
                         </div>
                         <input type="range" min="0" max="1" step="0.05" value={customWeights[fk as keyof typeof customWeights]} onChange={(e) => setCustomWeights(prev => ({...prev, [fk]: parseFloat(e.target.value)}))} className="w-full h-1.5 bg-neutral-200 rounded-lg appearance-none cursor-pointer accent-neutral-900 hover:accent-neutral-700 transition-all"/>
                       </div>
                     );
                   })}
                 </div>
                 {Object.values(customWeights).reduce((a, b) => a + b, 0) === 0 && (
                   <div className="mt-6 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-md">Error: At least one factor must have a weight &gt; 0.</div>
                 )}
              </div>

              <div className="md:col-span-2 space-y-6">
                 <div className="grid grid-cols-2 gap-4">
                    <div className="bg-white border border-neutral-200 rounded-lg p-5">
                      <span className="block text-[10px] uppercase tracking-wider text-neutral-400 mb-2">7a. Equal-Weight Baseline</span>
                      <span className="text-3xl font-semibold tracking-tight">{dashboard.baseline.score !== null ? dashboard.baseline.score.toFixed(3) : 'N/A'}</span>
                      <span className="block text-xs text-neutral-400 mt-2 font-mono">{dashboard.baseline.missing_factors.length > 0 ? `Renormalized (Missing: ${dashboard.baseline.missing_factors.join(',')})` : 'All 5 factors included'}</span>
                    </div>
                    
                    <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-5 text-white shadow-md relative overflow-hidden">
                      <span className="block text-[10px] uppercase tracking-wider text-neutral-400 mb-2">7b. Adjusted Trust Index</span>
                      <span className="text-3xl font-semibold tracking-tight">{dashboard.adjusted.score !== null ? dashboard.adjusted.score.toFixed(3) : 'N/A'}</span>
                      
                      {dashboard.comparison.signed_difference !== null && (
                        <div className="absolute top-5 right-5 text-xs font-mono">
                          <span className={dashboard.comparison.signed_difference > 0 ? 'text-emerald-400' : dashboard.comparison.signed_difference < 0 ? 'text-rose-400' : 'text-neutral-400'}>
                            {dashboard.comparison.signed_difference > 0 ? '+' : ''}{dashboard.comparison.signed_difference.toFixed(3)}
                          </span>
                        </div>
                      )}
                      <span className="block text-xs text-neutral-400 mt-2 font-mono">Recalculated with custom configuration</span>
                    </div>
                 </div>

                 {/* Section 8: Zero-Centered Contribution Bar Chart */}
                 <div className="bg-white border border-neutral-200 rounded-lg overflow-hidden">
                    <div className="border-b border-neutral-100 bg-neutral-50 p-4">
                      <h4 className="text-xs font-medium text-neutral-700">8. Factor Contributions to the Trust Evidence Index</h4>
                    </div>
                    <div className="p-4 space-y-5">
                       {Object.keys(initialWeights).map(fk => {
                         const effWeight = dashboard.adjusted.effective_weights[fk];
                         const contrib = dashboard.adjusted.contributions[fk];
                         const rawScore = dashboard.factor_scores[fk].score;
                         
                         // 格式化名称：如 "F1_functional_value" -> "F1 · Functional value"
                         const fParts = fk.split('_');
                         const fId = fParts[0];
                         const fName = fParts.slice(1).join(' ');
                         const displayName = `${fId} · ${fName.charAt(0).toUpperCase() + fName.slice(1)}`;
                         
                         // 未被包含的因子处理
                         if (effWeight === undefined) return (
                           <div key={fk} className="flex items-center gap-4 text-xs text-neutral-400 font-mono">
                              <span className="w-48 truncate">{displayName}</span>
                              <span>[Excluded due to missing data in subset]</span>
                           </div>
                         );

                         return (
                           <div 
                             key={fk} 
                             className="flex items-center gap-4 text-xs group cursor-default" 
                             // 悬停提示中显示具体算式
                             title={`Score (${rawScore?.toFixed(2)}) × Weight (${(effWeight).toFixed(2)}) = ${contrib > 0 ? '+' : ''}${contrib?.toFixed(3)}`}
                           >
                              <span className="w-48 truncate font-mono text-neutral-700">{displayName}</span>
                              
                              <div className="flex-1 flex items-center relative h-6 bg-neutral-50/50 rounded-sm border border-neutral-100">
                                 <div className="absolute top-0 bottom-0 left-[50%] w-px bg-neutral-300 z-10" />
                                 {contrib !== null && contrib !== 0 && (
                                    contrib > 0 
                                      ? <div className="absolute left-[50%] h-full bg-emerald-400 rounded-r-sm transition-all duration-300" style={{ width: `${contrib * 50}%` }} />
                                      : <div className="absolute right-[50%] h-full bg-rose-400 rounded-l-sm transition-all duration-300" style={{ width: `${Math.abs(contrib) * 50}%` }} />
                                 )}
                              </div>
                              
                              <div className="w-16 text-right font-mono font-medium text-neutral-700">
                                {contrib > 0 ? '+' : ''}{contrib?.toFixed(3)}
                              </div>
                           </div>
                         );
                       })}
                    </div>
                    {/* 底部动态总和显示 */}
                    <div className="bg-neutral-50 border-t border-neutral-100 p-3 pr-8 text-right text-xs text-neutral-600 font-mono">
                      Sum of contributions = {dashboard.adjusted.score !== null ? dashboard.adjusted.score.toFixed(3) : 'N/A'}
                    </div>
                 </div>
              </div>
            </div>

            {/* 9. Calculation Transparency Panel */}
            <div className="bg-neutral-50 border border-neutral-200 rounded-lg p-5">
              <h3 className="text-sm font-semibold uppercase tracking-widest text-neutral-600 mb-4">9. Calculation Methodology & Research Assumptions</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs text-neutral-600 leading-relaxed">
                <div>
                  <strong className="block mb-1 text-neutral-800">Factor-Level Calculation</strong> Factor scores represent the average encoded sentiment polarity among reviews explicitly mentioning each factor.
                  <strong className="block mb-1 mt-4 text-neutral-800">Sentiment Distribution</strong> Shows the proportion of positive, neutral, and negative observations calculated independent of index weights.
                  <strong className="block mb-1 mt-4 text-neutral-800">Dynamic Renormalization</strong> Unavailable factors are excluded from weighted aggregation, and remaining weights are renormalized to sum to 1.
                </div>
                <div>
                  <strong className="block mb-1 text-neutral-800">Weighted Trust Index</strong> Combines available factor sentiment scores using explicitly defined normalized weights.
                  <strong className="block mb-1 mt-4 text-neutral-800">Sensitivity Analysis</strong> Examines how the composite index responds to alternative assumptions about factor importance without altering underlying data.
                  <strong className="block mb-1 mt-4 text-rose-800">Research Limitation</strong> The composite index is an operational measure of trust-related sentiment in reviews. It is not an independently validated psychological measure of customer trust.
                </div>
              </div>
            </div>

          </div>
        ) : (
          <div className="text-center p-12 text-sm text-neutral-500">Loading Dashboard Context...</div>
        )) : (
          
          // ============================================================================
          // EXPLORER VIEW (Dataset Annotation & Management)
          // ============================================================================
          <div className="space-y-8 animate-in fade-in duration-500">
            
            {/* Input and Submission Area */}
            <div className="bg-white border border-neutral-200 rounded-lg overflow-hidden p-5 shadow-sm relative">
              {/* Top loading animation bar (shows only when processing) */}
              {loadingType && (
                 <div className="absolute top-0 left-0 right-0 h-1 bg-neutral-100 overflow-hidden">
                    <div className="h-full bg-black w-1/3 animate-[pulse_1s_ease-in-out_infinite]" />
                 </div>
              )}
              
              <textarea 
                value={input} 
                onChange={(e) => setInput(e.target.value)} 
                disabled={loadingType !== null}
                placeholder="Paste review text here... (Support batch queue via new lines)" 
                className="w-full min-h-[120px] text-sm outline-none resize-y disabled:opacity-50 disabled:bg-neutral-50 transition-colors"
              />
              
              <div className="flex items-center justify-between border-t border-neutral-100 pt-3 mt-2">
                <span className="text-xs font-medium px-2 py-1 text-neutral-600">{status.msg}</span>
                <div className="flex gap-2">
                  
                  {/* Cancel Button */}
                  {loadingType !== null && (
                    <button 
                      onClick={handleCancel} 
                      className="px-5 py-2 bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 text-xs font-medium rounded-md transition-all"
                    >
                      Cancel Process
                    </button>
                  )}
                  
                  <button 
                    onClick={() => submitAction(false)} 
                    disabled={loadingType !== null} 
                    className="px-5 py-2 bg-neutral-100 hover:bg-neutral-200 text-neutral-900 text-xs font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    {loadingType === 'single' ? 'Processing...' : 'Run Single'}
                  </button>
                  <button 
                    onClick={() => submitAction(true)} 
                    disabled={loadingType !== null} 
                    className="px-5 py-2 bg-black hover:bg-neutral-800 text-white text-xs font-medium rounded-md min-w-[140px] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    {loadingType === 'batch' ? 'Processing Batch...' : 'Run Batch Queue'}
                  </button>
                </div>
              </div>
            </div>

            {/* List Rendering and Editor */}
            <div className="space-y-6">
              {notes.map(note => {
                const data = note.human_parsed_data || note.llm_parsed_data;
                return (
                <div key={note.id} className="bg-white border border-neutral-200 rounded-lg p-6 shadow-sm transition-all hover:shadow-md">
                  <div className="flex justify-between items-start mb-6">
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono text-neutral-400">#{note.id.slice(-6)}</span>
                      <span className={`text-[11px] font-medium px-2 py-0.5 border rounded-full ${note.verification_status.includes('human') ? 'bg-white text-neutral-900 border-neutral-300' : note.verification_status === 'raw' ? 'bg-red-50 text-red-600 border-red-200' : 'bg-neutral-50 text-neutral-500 border-neutral-200'}`}>
                        {note.verification_status.includes('human') ? 'Human Verified' : note.verification_status === 'raw' ? 'AI Failed' : 'Pending Review'}
                      </span>
                    </div>
                    <button onClick={() => deleteNote(note.id)} className="text-xs text-neutral-400 hover:text-rose-600 transition-colors">Delete</button>
                  </div>
                  <pre className="whitespace-pre-wrap font-sans text-sm text-neutral-700 bg-neutral-50 border border-neutral-100 p-4 rounded-md mb-6">{note.content}</pre>
                  
                  {data && (
                    <div className="border border-neutral-200 rounded-md overflow-hidden bg-white">
                      {editingId === note.id && editForm ? (
                        <div className="text-sm">
                          <div className="flex justify-between p-4 border-b border-neutral-200 bg-neutral-50">
                            <span className="font-medium text-xs uppercase tracking-widest text-neutral-500">Editor</span>
                            <button onClick={() => setEditingId(null)} className="text-neutral-500 hover:text-neutral-900 text-xs transition-colors">Cancel</button>
                          </div>
                          <div className="p-4 space-y-3">
                            {Object.entries(editForm.factors).map(([k, f]) => (
                              <div key={k} className="flex justify-between items-center border border-neutral-100 p-3 rounded-md hover:bg-neutral-50 transition-colors">
                                <div>
                                    <span className="text-neutral-700 block text-xs font-mono mb-1">{k.replace('F', 'F').replace(/_/g, ' ')}</span>
                                    <button 
                                      onClick={() => toggleMention(k)} 
                                      className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${f.mentioned ? 'bg-neutral-50 border-neutral-200 text-neutral-900' : 'bg-white border-dashed border-neutral-300 text-neutral-400 hover:bg-neutral-100'}`}
                                    >
                                      {f.mentioned ? 'MENTIONED' : 'UNMENTIONED'}
                                    </button>
                                </div>
                                {f.mentioned && (
                                    <div className="flex items-center border border-neutral-200 rounded-md overflow-hidden h-8">
                                      <button onClick={() => setPolarity(k, (f.polarity || 0) - 1)} disabled={f.polarity === -1} className="w-8 h-full text-neutral-500 hover:bg-neutral-100 transition-colors border-r border-neutral-200 disabled:opacity-30 disabled:cursor-not-allowed">-</button>
                                      <span className="w-12 h-full flex items-center justify-center font-mono text-neutral-900 text-sm bg-white">{f.polarity || 0}</span>
                                      <button onClick={() => setPolarity(k, (f.polarity || 0) + 1)} disabled={f.polarity === 1} className="w-8 h-full text-neutral-500 hover:bg-neutral-100 transition-colors border-l border-neutral-200 disabled:opacity-30 disabled:cursor-not-allowed">+</button>
                                    </div>
                                )}
                              </div>
                            ))}
                          </div>
                          <div className="p-4 border-t border-neutral-200 bg-neutral-50 flex justify-end">
                            <button onClick={() => saveVerification(note.id)} className="px-5 py-2 bg-black text-white text-xs font-medium rounded-md hover:bg-neutral-800 transition-colors">Save Verification</button>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <div className="bg-neutral-50 p-4 flex justify-between border-b border-neutral-200">
                            <span className="text-neutral-500 text-xs uppercase tracking-widest">Dataset Map</span>
                            <button onClick={() => { setEditingId(note.id); setEditForm(JSON.parse(JSON.stringify(data))); }} className="text-xs border border-neutral-200 bg-white text-neutral-700 px-3 py-1.5 rounded-md hover:bg-neutral-100 transition-colors shadow-sm">Verify & Edit</button>
                          </div>
                          <div className="p-4 flex flex-wrap gap-2">
                             {Object.entries(data.factors).map(([k, f]) => {
                                if (!f.mentioned) return null;
                                let colorClass = "bg-neutral-100 text-neutral-600 border-neutral-200";
                                if (f.polarity === 1) colorClass = "bg-emerald-50 text-emerald-700 border-emerald-200";
                                if (f.polarity === -1) colorClass = "bg-rose-50 text-rose-700 border-rose-200";
                                return (
                                  <span key={k} className={`text-[10px] px-2 py-1 rounded-full border font-mono ${colorClass}`}>
                                    {k.split('_')[0]}: {f.polarity === 1 ? 'POS' : f.polarity === -1 ? 'NEG' : 'NEU'}
                                  </span>
                                );
                             })}
                             {Object.values(data.factors).every(f => !f.mentioned) && (
                               <span className="text-xs text-neutral-400 italic">No trust factors mentioned in this review.</span>
                             )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )})}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
