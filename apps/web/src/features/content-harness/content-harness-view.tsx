"use client";

import { useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Code2,
  Cpu,
  FileText,
  Flame,
  HelpCircle,
  Layers,
  Link as LinkIcon,
  Play,
  RotateCcw,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

interface GoldenCaseOption {
  case_id: string;
  name: string;
  primary_keyword: string;
  secondary_keywords: string[];
  target_audience: string;
  target_word_count: number;
  prompt_version: string;
  brand_tone: string;
  forbidden_words: string[];
  internal_links_count: number;
}

interface HarnessFinding {
  category: string;
  rule: string;
  status: "PASS" | "FAIL" | "WARN";
  impact: "HIGH" | "MEDIUM" | "LOW" | "INFO";
  message: string;
  details?: Record<string, unknown>;
}

interface HarnessScorecard {
  seo_score: number;
  content_score: number;
  brand_score: number;
  linking_score: number;
  technical_validity: "PASS" | "FAIL";
  overall_score: number;
  status: "PASS" | "NEEDS IMPROVEMENT";
  findings: HarnessFinding[];
  summary: string;
  ai_evaluation?: Record<string, unknown>;
}

interface RunDetail {
  id: string;
  name: string;
  status: string;
  prompt_version: string;
  model: string;
  provider: string;
  score?: number;
  output_data: {
    title?: string;
    meta_description?: string;
    content?: string;
    sections?: Array<{ heading: string; level: number; content: string }>;
    used_keywords?: string[];
    internal_links?: Array<{ url: string; anchor_text: string }>;
    word_count?: number;
    raw_text?: string;
    error?: string;
  };
  prompt_data: {
    system_prompt?: string;
    user_prompt?: string;
    version?: string;
  };
  context_data: Record<string, unknown>;
  evaluation_data: HarnessScorecard;
  created_at: string;
}

interface ComparisonResult {
  run_a: RunDetail;
  run_b: RunDetail;
  score_diffs: Record<string, number>;
  improvements: string[];
  regressions: string[];
  summary: string;
}

export function ContentHarnessView({
  projectId,
  goldenCases,
  initialRuns,
}: {
  projectId: string;
  goldenCases: GoldenCaseOption[];
  initialRuns: RunDetail[];
}) {
  const [activeTab, setActiveTab] = useState<"input" | "output" | "scorecard" | "compare" | "inspect">("input");
  const [selectedCaseId, setSelectedCaseId] = useState<string>("");

  // Form states
  const [name, setName] = useState("Fleet Vehicle Tracking Test");
  const [primaryKeyword, setPrimaryKeyword] = useState("fleet vehicle tracking");
  const [secondaryKeywords, setSecondaryKeywords] = useState("gps tracking, fleet monitoring, telematics");
  const [targetAudience, setTargetAudience] = useState("Fleet managers and logistics leads");
  const [targetWordCount, setTargetWordCount] = useState(1200);
  const [promptVersion, setPromptVersion] = useState("v1");
  const [brandTone, setBrandTone] = useState("Professional, practical, authoritative");
  const [wordsToAvoid, setWordsToAvoid] = useState("cheap, miracle, guaranteed");
  const [websiteContext, setWebsiteContext] = useState(
    "FleetIQ provides cloud telematics, real-time GPS fleet tracking, and automated maintenance schedules."
  );
  const [runAiEvaluator, setRunAiEvaluator] = useState(false);

  // Execution states
  const [isRunning, setIsRunning] = useState(false);
  const [currentRun, setCurrentRun] = useState<RunDetail | null>(initialRuns[0] || null);
  const [runsList, setRunsList] = useState<RunDetail[]>(initialRuns);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // Comparison states
  const [compareAId, setCompareAId] = useState<string>(initialRuns[0]?.id || "");
  const [compareBId, setCompareBId] = useState<string>(initialRuns[1]?.id || initialRuns[0]?.id || "");
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [isComparing, setIsComparing] = useState(false);

  // Load a golden case into form
  const handleSelectGoldenCase = (caseId: string) => {
    setSelectedCaseId(caseId);
    const found = goldenCases.find((c) => c.case_id === caseId);
    if (found) {
      setName(found.name);
      setPrimaryKeyword(found.primary_keyword);
      setSecondaryKeywords(found.secondary_keywords.join(", "));
      setTargetAudience(found.target_audience);
      setTargetWordCount(found.target_word_count);
      setPromptVersion(found.prompt_version);
      setBrandTone(found.brand_tone);
      setWordsToAvoid(found.forbidden_words.join(", "));
    }
  };

  // Run Content Harness
  const handleRunHarness = async () => {
    setIsRunning(true);
    setErrorBanner(null);
    try {
      const payload = {
        project_id: projectId,
        name,
        primary_keyword: primaryKeyword.trim(),
        secondary_keywords: secondaryKeywords.split(",").map((k) => k.trim()).filter(Boolean),
        search_intent: "INFORMATIONAL",
        target_audience: targetAudience,
        target_word_count: Number(targetWordCount),
        prompt_version: promptVersion,
        brand_rules: {
          tone: brandTone,
          voice: "Domain Expert",
          style: "Clear, structured, actionable",
          words_to_avoid: wordsToAvoid.split(",").map((w) => w.trim()).filter(Boolean),
          formatting_rules: ["H2 headings", "Clear paragraphs"],
        },
        internal_link_targets: [
          {
            url: "/telematics-platform",
            anchor_text: "telematics platform",
            reason: "Pillar page connection",
          },
        ],
        website_context: websiteContext,
        run_ai_evaluator: runAiEvaluator,
      };

      const res = await fetch(`/api/backend/content-harness/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok || !data.data) {
        throw new Error(data.errors?.[0]?.message || "Harness execution failed.");
      }

      const newRun: RunDetail = data.data;
      setCurrentRun(newRun);
      setRunsList((prev) => [newRun, ...prev]);
      setActiveTab("scorecard");
    } catch (err: unknown) {
      setErrorBanner(err instanceof Error ? err.message : String(err));
    } finally {
      setIsRunning(false);
    }
  };

  // Compare two runs
  const handleCompare = async () => {
    if (!compareAId || !compareBId) return;
    setIsComparing(true);
    try {
      const res = await fetch(`/api/backend/content-harness/runs/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          run_id_a: compareAId,
          run_id_b: compareBId,
        }),
      });
      const data = await res.json();
      if (res.ok && data.data) {
        setComparison(data.data);
      }
    } catch (err) {
      console.error("Comparison error:", err);
    } finally {
      setIsComparing(false);
    }
  };

  const scorecard = currentRun?.evaluation_data;
  const output = currentRun?.output_data;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-[var(--border)] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">
              <Sparkles size={13} /> Testing & Evaluation Lab
            </span>
            <span className="text-xs text-[var(--muted)]">Isolated Environment</span>
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-[var(--ink)]">AI Content Harness</h1>
          <p className="text-sm text-[var(--muted)]">
            Test and evaluate content generation deterministically without mutating live production documents.
          </p>
        </div>

        {/* Action button */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleRunHarness}
            disabled={isRunning}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[var(--accent-strong)] disabled:opacity-50"
          >
            {isRunning ? (
              <>
                <RotateCcw size={16} className="animate-spin" /> Running Harness...
              </>
            ) : (
              <>
                <Play size={16} /> Run Content Harness
              </>
            )}
          </button>
        </div>
      </div>

      {errorBanner && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <AlertCircle size={18} className="shrink-0" />
          <span>{errorBanner}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-[var(--border)] pb-2 text-sm font-medium text-[var(--muted)]">
        {[
          { id: "input", label: "Harness Input", icon: Layers },
          { id: "scorecard", label: "Scorecard & Findings", icon: CheckCircle2 },
          { id: "output", label: "Generated Output", icon: FileText },
          { id: "compare", label: "Compare Runs", icon: ArrowRight },
          { id: "inspect", label: "Inspect Prompt & Context", icon: Code2 },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center gap-2 rounded-md px-3.5 py-1.5 transition ${
                isActive
                  ? "bg-white font-semibold text-[var(--ink)] shadow-sm"
                  : "hover:bg-white/60 hover:text-[var(--ink)]"
              }`}
            >
              <Icon size={15} />
              {tab.label}
              {tab.id === "scorecard" && scorecard && (
                <span
                  className={`ml-1 rounded-full px-1.5 py-0.2 text-[11px] font-bold ${
                    scorecard.status === "PASS" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                  }`}
                >
                  {scorecard.overall_score}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* TAB 1: INPUT */}
      {activeTab === "input" && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Quick golden case picker */}
          <div className="space-y-4 rounded-xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--muted)]">
              Standard Golden Test Cases
            </h2>
            <p className="text-xs text-[var(--muted)]">
              Click any pre-configured case to load verified benchmark parameters:
            </p>
            <div className="space-y-2">
              {goldenCases.map((gc) => (
                <button
                  key={gc.case_id}
                  onClick={() => handleSelectGoldenCase(gc.case_id)}
                  className={`w-full text-left rounded-lg border p-3 text-xs transition ${
                    selectedCaseId === gc.case_id
                      ? "border-indigo-500 bg-indigo-50/50 shadow-sm"
                      : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                  }`}
                >
                  <div className="font-semibold text-[var(--ink)]">{gc.name}</div>
                  <div className="mt-1 text-[var(--muted)]">KW: &ldquo;{gc.primary_keyword}&rdquo;</div>
                  <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
                    <span>Target: {gc.target_word_count}w</span>
                    <span>•</span>
                    <span>Prompt: {gc.prompt_version}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Input form */}
          <div className="space-y-4 rounded-xl border border-[var(--border)] bg-white p-6 shadow-sm lg:col-span-2">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="block text-xs font-bold text-[var(--ink)]">Test Run Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm shadow-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-[var(--ink)]">Primary Keyword</label>
                <input
                  type="text"
                  value={primaryKeyword}
                  onChange={(e) => setPrimaryKeyword(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm shadow-sm"
                  placeholder="e.g. fleet vehicle tracking"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-[var(--ink)]">Target Audience</label>
                <input
                  type="text"
                  value={targetAudience}
                  onChange={(e) => setTargetAudience(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm shadow-sm"
                  placeholder="e.g. Fleet managers"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="block text-xs font-bold text-[var(--ink)]">Secondary Keywords (comma separated)</label>
                <input
                  type="text"
                  value={secondaryKeywords}
                  onChange={(e) => setSecondaryKeywords(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm shadow-sm"
                  placeholder="gps tracking, vehicle monitoring, route optimization"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-[var(--ink)]">Target Word Count</label>
                <input
                  type="number"
                  value={targetWordCount}
                  onChange={(e) => setTargetWordCount(Number(e.target.value))}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm shadow-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-[var(--ink)]">Prompt Version</label>
                <select
                  value={promptVersion}
                  onChange={(e) => setPromptVersion(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm shadow-sm"
                >
                  <option value="v1">Prompt V1 (Standard Structured Output)</option>
                  <option value="v2">Prompt V2 (Enhanced Negative Constraints & Anchors)</option>
                </select>
              </div>

              <div className="sm:col-span-2">
                <label className="block text-xs font-bold text-[var(--ink)]">Brand Tone & Voice</label>
                <input
                  type="text"
                  value={brandTone}
                  onChange={(e) => setBrandTone(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm shadow-sm"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="block text-xs font-bold text-[var(--ink)]">
                  Words to Avoid (Strictly Forbidden, comma separated)
                </label>
                <input
                  type="text"
                  value={wordsToAvoid}
                  onChange={(e) => setWordsToAvoid(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm shadow-sm"
                  placeholder="cheap, miracle, guaranteed, easy money"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="block text-xs font-bold text-[var(--ink)]">Relevant Website Context</label>
                <textarea
                  rows={3}
                  value={websiteContext}
                  onChange={(e) => setWebsiteContext(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm shadow-sm"
                  placeholder="Enter business details or product facts that the AI should ground on..."
                />
              </div>

              <div className="sm:col-span-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  id="runAiEval"
                  checked={runAiEvaluator}
                  onChange={(e) => setRunAiEvaluator(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <label htmlFor="runAiEval" className="text-xs text-[var(--ink)]">
                  Enable optional qualitative AI evaluation (checks tone nuances and hallucination risk)
                </label>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: SCORECARD */}
      {activeTab === "scorecard" && (
        <div className="space-y-6">
          {!scorecard ? (
            <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-12 text-center text-sm text-[var(--muted)]">
              No run executed yet. Select a Golden Case or configure inputs and click &ldquo;Run Content Harness&rdquo;.
            </div>
          ) : (
            <>
              {/* Scorecard Summary Metrics */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
                <div className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
                  <div className="text-xs font-medium text-[var(--muted)]">Overall Status</div>
                  <div
                    className={`mt-2 text-lg font-bold ${
                      scorecard.status === "PASS" ? "text-emerald-600" : "text-amber-600"
                    }`}
                  >
                    {scorecard.status}
                  </div>
                  <div className="mt-1 text-xs text-[var(--muted)]">{scorecard.overall_score}/100</div>
                </div>

                <div className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
                  <div className="text-xs font-medium text-[var(--muted)]">SEO Score</div>
                  <div className="mt-2 text-2xl font-bold text-indigo-600">{scorecard.seo_score}</div>
                  <div className="mt-1 text-[11px] text-[var(--muted)]">Target: 75+</div>
                </div>

                <div className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
                  <div className="text-xs font-medium text-[var(--muted)]">Content Coverage</div>
                  <div className="mt-2 text-2xl font-bold text-blue-600">{scorecard.content_score}</div>
                  <div className="mt-1 text-[11px] text-[var(--muted)]">Topics & Word Count</div>
                </div>

                <div className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
                  <div className="text-xs font-medium text-[var(--muted)]">Brand Compliance</div>
                  <div
                    className={`mt-2 text-2xl font-bold ${
                      scorecard.brand_score >= 80 ? "text-emerald-600" : "text-red-600"
                    }`}
                  >
                    {scorecard.brand_score}
                  </div>
                  <div className="mt-1 text-[11px] text-[var(--muted)]">Words to Avoid</div>
                </div>

                <div className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
                  <div className="text-xs font-medium text-[var(--muted)]">Internal Links</div>
                  <div className="mt-2 text-2xl font-bold text-teal-600">{scorecard.linking_score}</div>
                  <div className="mt-1 text-[11px] text-[var(--muted)]">Target Anchors & URLs</div>
                </div>

                <div className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
                  <div className="text-xs font-medium text-[var(--muted)]">Technical Validity</div>
                  <div
                    className={`mt-2 text-lg font-bold ${
                      scorecard.technical_validity === "PASS" ? "text-emerald-600" : "text-red-600"
                    }`}
                  >
                    {scorecard.technical_validity}
                  </div>
                  <div className="mt-1 text-[11px] text-[var(--muted)]">Schema Parsed</div>
                </div>
              </div>

              {/* Detailed Findings */}
              <div className="rounded-xl border border-[var(--border)] bg-white p-6 shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h3 className="font-bold text-[var(--ink)]">Deterministic Evaluation Findings</h3>
                  <span className="text-xs text-[var(--muted)]">
                    {scorecard.findings.length} verification checks executed
                  </span>
                </div>

                <div className="mt-4 divide-y divide-slate-100">
                  {scorecard.findings.map((finding, idx) => (
                    <div key={idx} className="flex items-start justify-between py-3">
                      <div className="flex items-start gap-3">
                        {finding.status === "PASS" && <CheckCircle2 size={18} className="text-emerald-500 mt-0.5" />}
                        {finding.status === "WARN" && <AlertCircle size={18} className="text-amber-500 mt-0.5" />}
                        {finding.status === "FAIL" && <ShieldAlert size={18} className="text-red-500 mt-0.5" />}

                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                              [{finding.category}]
                            </span>
                            <span className="text-sm font-semibold text-[var(--ink)]">{finding.rule}</span>
                            <span
                              className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                                finding.impact === "HIGH"
                                  ? "bg-red-100 text-red-700"
                                  : finding.impact === "MEDIUM"
                                  ? "bg-amber-100 text-amber-700"
                                  : "bg-slate-100 text-slate-600"
                              }`}
                            >
                              {finding.impact} Impact
                            </span>
                          </div>
                          <p className="mt-0.5 text-xs text-slate-600">{finding.message}</p>
                        </div>
                      </div>

                      <span
                        className={`rounded-full px-2.5 py-0.5 text-xs font-bold uppercase ${
                          finding.status === "PASS"
                            ? "bg-emerald-50 text-emerald-700"
                            : finding.status === "WARN"
                            ? "bg-amber-50 text-amber-700"
                            : "bg-red-50 text-red-700"
                        }`}
                      >
                        {finding.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Optional AI Evaluation feedback if present */}
              {scorecard.ai_evaluation && (
                <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-6 shadow-sm">
                  <div className="flex items-center gap-2">
                    <Sparkles size={16} className="text-indigo-600" />
                    <h3 className="font-bold text-indigo-950">Qualitative AI Evaluator Insights</h3>
                  </div>
                  <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-4 text-xs text-slate-800 border border-indigo-100">
                    {JSON.stringify(scorecard.ai_evaluation, null, 2)}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* TAB 3: GENERATED OUTPUT */}
      {activeTab === "output" && (
        <div className="space-y-6">
          {!output ? (
            <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-12 text-center text-sm text-[var(--muted)]">
              No generated content available.
            </div>
          ) : (
            <div className="rounded-xl border border-[var(--border)] bg-white p-8 shadow-sm space-y-6">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-indigo-600">Generated Title</span>
                <h1 className="mt-1 text-2xl font-bold text-[var(--ink)]">{output.title}</h1>
              </div>

              {output.meta_description && (
                <div className="rounded-lg bg-slate-50 p-4 border border-slate-200">
                  <span className="text-xs font-bold text-slate-500 uppercase">Meta Description</span>
                  <p className="mt-1 text-sm text-slate-700">{output.meta_description}</p>
                </div>
              )}

              {output.used_keywords && output.used_keywords.length > 0 && (
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Keywords Used</span>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {output.used_keywords.map((kw, idx) => (
                      <span
                        key={idx}
                        className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 border border-indigo-200"
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {output.internal_links && output.internal_links.length > 0 && (
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                    Internal Links Included
                  </span>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {output.internal_links.map((link, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1.5 rounded bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-800 border border-teal-200"
                      >
                        <LinkIcon size={12} /> {link.anchor_text} &rarr; {link.url}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="border-t border-slate-100 pt-6">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Structured Sections</span>
                <div className="mt-4 space-y-6">
                  {output.sections?.map((sec, idx) => (
                    <div key={idx} className="space-y-2">
                      <h2 className="text-lg font-bold text-[var(--ink)]">{sec.heading}</h2>
                      <p className="text-sm leading-relaxed text-slate-700 whitespace-pre-line">{sec.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: COMPARE RUNS */}
      {activeTab === "compare" && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row items-end gap-4 rounded-xl border border-[var(--border)] bg-white p-5 shadow-sm">
            <div className="flex-1">
              <label className="block text-xs font-bold text-[var(--ink)]">Run A (Baseline)</label>
              <select
                value={compareAId}
                onChange={(e) => setCompareAId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm"
              >
                {runsList.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.prompt_version}, Score: {r.score ?? "N/A"})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex-1">
              <label className="block text-xs font-bold text-[var(--ink)]">Run B (Comparison)</label>
              <select
                value={compareBId}
                onChange={(e) => setCompareBId(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-300 p-2 text-sm"
              >
                {runsList.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.prompt_version}, Score: {r.score ?? "N/A"})
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={handleCompare}
              disabled={isComparing || !compareAId || !compareBId}
              className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {isComparing ? "Comparing..." : "Compare Runs"}
            </button>
          </div>

          {comparison && (
            <div className="space-y-6">
              {/* Score Diff Grid */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                {[
                  { label: "Overall Score", key: "overall" },
                  { label: "SEO Score", key: "seo" },
                  { label: "Content Score", key: "content" },
                  { label: "Brand Score", key: "brand" },
                  { label: "Internal Links", key: "linking" },
                ].map((metric) => {
                  const diff = comparison.score_diffs[metric.key] || 0;
                  const isPositive = diff > 0;
                  const isZero = diff === 0;
                  return (
                    <div key={metric.key} className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm">
                      <div className="text-xs text-[var(--muted)]">{metric.label} Delta</div>
                      <div
                        className={`mt-2 flex items-center gap-1.5 text-xl font-bold ${
                          isPositive ? "text-emerald-600" : isZero ? "text-slate-600" : "text-red-600"
                        }`}
                      >
                        {isPositive ? <TrendingUp size={18} /> : !isZero ? <TrendingDown size={18} /> : null}
                        {diff > 0 ? `+${diff}` : diff} pts
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Improvements and Regressions */}
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-5 shadow-sm">
                  <h4 className="flex items-center gap-2 text-sm font-bold text-emerald-900">
                    <CheckCircle2 size={16} /> Improvements in Run B ({comparison.improvements.length})
                  </h4>
                  {comparison.improvements.length === 0 ? (
                    <p className="mt-2 text-xs text-emerald-700">No new rules improved.</p>
                  ) : (
                    <ul className="mt-3 space-y-1 text-xs text-emerald-800 list-disc pl-4">
                      {comparison.improvements.map((imp, idx) => (
                        <li key={idx}>{imp}</li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="rounded-xl border border-red-200 bg-red-50/40 p-5 shadow-sm">
                  <h4 className="flex items-center gap-2 text-sm font-bold text-red-900">
                    <AlertCircle size={16} /> Regressions in Run B ({comparison.regressions.length})
                  </h4>
                  {comparison.regressions.length === 0 ? (
                    <p className="mt-2 text-xs text-red-700">Zero regressions detected!</p>
                  ) : (
                    <ul className="mt-3 space-y-1 text-xs text-red-800 list-disc pl-4">
                      {comparison.regressions.map((reg, idx) => (
                        <li key={idx}>{reg}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: INSPECT PROMPT & CONTEXT */}
      {activeTab === "inspect" && (
        <div className="space-y-6">
          {!currentRun ? (
            <div className="rounded-xl border border-dashed border-[var(--border)] bg-white p-12 text-center text-sm text-[var(--muted)]">
              No run details available.
            </div>
          ) : (
            <div className="space-y-6">
              <div className="rounded-xl border border-[var(--border)] bg-white p-6 shadow-sm">
                <h3 className="font-bold text-[var(--ink)]">System Prompt (Version {currentRun.prompt_version})</h3>
                <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100 whitespace-pre-wrap">
                  {currentRun.prompt_data?.system_prompt || "None"}
                </pre>
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-white p-6 shadow-sm">
                <h3 className="font-bold text-[var(--ink)]">User Prompt</h3>
                <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100 whitespace-pre-wrap">
                  {currentRun.prompt_data?.user_prompt || "None"}
                </pre>
              </div>

              <div className="rounded-xl border border-[var(--border)] bg-white p-6 shadow-sm">
                <h3 className="font-bold text-[var(--ink)]">Context Snapshot</h3>
                <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-50 p-4 text-xs text-slate-800 border border-slate-200">
                  {JSON.stringify(currentRun.context_data, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
