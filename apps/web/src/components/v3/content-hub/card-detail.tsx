"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { CardCheck, CardDetail, G1Reason, G2Reason, OutlineV3 } from "@/lib/api-types";
import { ApiError } from "@/lib/client-api";
import { V3API, type V3Scope } from "@/lib/v3-api";

import { DraftView } from "./draft-view";
import { G1ReviewPanel, G1StatusChip, decisionLine, formatWhen } from "./g1-review";
import { G2ReviewPanel, G2StatusChip } from "./g2-review";
import { QAChip, QAPanel, qaChipState } from "./qa-panel";
import { OutlineEditor, blankOutline, type PageOption } from "./outline-editor";

const CONFLICT_MESSAGE = "Your version is out of date. Reload before saving.";

const PROVIDER_LABEL: Record<string, string> = { gemini: "Google Gemini", anthropic: "Anthropic Claude" };

type Busy =
  | "bundle"
  | "generate"
  | "save"
  | "approve"
  | "sendback"
  | "draft"
  | "qa"
  | "repair"
  | "regen"
  | "dismiss"
  | "g2approve"
  | "g2sendback";

const PRODUCTION_STATES = ["drafting", "qa_failed", "qa_passed", "approved", "live"];
const btn =
  "rounded-[5px] border border-[var(--line)] bg-white px-[10px] py-[4px] text-[12.5px] text-[#12171A] hover:bg-[#F0F2F1] focus-visible:outline-2 focus-visible:outline-[var(--teal)] disabled:opacity-50";
const btnPrimary =
  "rounded-[5px] border border-[var(--teal)] bg-[var(--teal)] px-[10px] py-[4px] text-[12.5px] text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--teal)] disabled:opacity-50";

interface Issue {
  code: string;
  message: string;
  section_id?: string | null;
}

function describe(error: unknown, fallback: string): { message: string; issues: Issue[] } {
  if (error instanceof ApiError) {
    if (error.code === "VERSION_CONFLICT") return { message: CONFLICT_MESSAGE, issues: [] };
    const issues = Array.isArray(error.details?.issues) ? (error.details.issues as Issue[]) : [];
    // G1_CHECKS_FAILED lists the failing checks instead of outline issues.
    const checks = Array.isArray(error.details?.checks) ? (error.details.checks as CardCheck[]) : [];
    for (const check of checks) {
      issues.push({ code: check.key, message: check.detail ? `${check.label}: ${check.detail}` : check.label });
    }
    return { message: error.message || fallback, issues };
  }
  return { message: error instanceof Error && error.message ? error.message : fallback, issues: [] };
}

function Pane({ title, chip, children }: { title: string; chip?: ReactNode; children: ReactNode }) {
  return (
    <section aria-label={title} className="min-w-0 rounded-[8px] border border-[var(--line)] bg-white">
      <header className="flex items-center gap-[8px] border-b border-[var(--line2)] px-[13px] py-[9px]">
        <h3 className="m-0 text-[13px] font-medium">{title}</h3>
        {chip}
      </header>
      <div className="p-[13px]">{children}</div>
    </section>
  );
}

function Block({ label, children, empty }: { label: string; children: ReactNode; empty: boolean }) {
  return (
    <div className="border-b border-[var(--line2)] py-[9px] last:border-b-0">
      <div className="mb-[4px] text-[11.5px] text-[var(--ink3)]">{label}</div>
      {empty ? <p className="m-0 text-[12.2px] text-[var(--ink3)]">No data configured</p> : children}
    </div>
  );
}

function ContextPane({ detail }: { detail: CardDetail }) {
  const c = detail.context;
  const brand = c.rules.brand;
  const pages = c.references.website.crawled_pages;
  const links = c.references.internal_linking.opportunities;
  const muted = "m-0 text-[12.2px] text-[#5C666C]";
  return (
    <Pane
      title="Context"
      chip={
        detail.bundle ? (
          <span className={`chip ${detail.bundle.is_current ? "t" : "c"}`}>
            {detail.bundle.is_current ? "stored bundle" : "bundle out of date"}
          </span>
        ) : (
          <span className="chip r">not bundled</span>
        )
      }
    >
      <div className="text-[12.5px]">
        <Block label="Strategy" empty={!c.pitch.argument_id && !c.demand.length}>
          {c.pitch.differentiation_pillar ? <p className={muted}>Argument · {c.pitch.differentiation_pillar}</p> : null}
          {c.demand.map((d) => (
            <p key={d.id} className={muted}>
              {d.role} · {d.text}
              {d.volume !== null ? ` · ${d.volume}` : ""}
              {d.citation_gap !== null ? ` · gap ${d.citation_gap}` : ""}
            </p>
          ))}
        </Block>
        <Block label={`Claims · ${c.claims.length} approved, current`} empty={!c.claims.length}>
          {c.claims.map((claim) => (
            <p key={claim.id} className="m-0 text-[12.2px]">
              <span className="font-mono text-[var(--teal)]">✓</span> {claim.text}{" "}
              <span className="text-[var(--ink3)]">v{claim.version}</span>
            </p>
          ))}
        </Block>
        <Block label="Brand" empty={!brand.tone && !brand.style && !brand.words_to_avoid.length && !c.tone.social_proof.length}>
          {brand.tone ? <p className={muted}>Tone · {brand.tone}</p> : null}
          {brand.style ? <p className={muted}>Style · {brand.style}</p> : null}
          {brand.formatting_rules.map((rule) => <p key={rule} className={muted}>{rule}</p>)}
          {brand.words_to_avoid.length ? <p className={muted}>Avoid · {brand.words_to_avoid.join(", ")}</p> : null}
          {c.tone.voice_snippets.length ? <p className={muted}>{c.tone.voice_snippets.length} voice snippet(s)</p> : null}
          {c.tone.social_proof.length ? <p className={muted}>Proof · {c.tone.social_proof.join(", ")}</p> : null}
        </Block>
        <Block label="Content" empty={!c.siblings.length}>
          {c.siblings.map((s) => <p key={s.id} className={muted}>{s.title} ({s.state})</p>)}
        </Block>
        <Block label="Linking" empty={!links.length}>
          {links.map((link) => <p key={link.id} className={muted}>→ {link.target_url || link.target_page_id}</p>)}
        </Block>
        <Block label="Website" empty={!pages.length}>
          {pages.map((page) => (
            <p key={page.url} className={muted} title={page.headings.join(" · ")}>
              {page.title || page.url} · {page.word_count} words
            </p>
          ))}
        </Block>
        <p className="m-[8px_0_0] text-[11px] text-[var(--ink3)]">
          Market {c.card.market ?? "—"} · {c.budget.used_tokens}/{c.budget.max_tokens} tokens
          {c.budget.truncated_sections.length ? ` · trimmed ${c.budget.truncated_sections.join(", ")}` : ""}
        </p>
      </div>
    </Pane>
  );
}

const CHECK_MARK: Record<CardCheck["status"], string> = { pass: "✓", fail: "✕", not_applicable: "–" };
const CHECK_TONE: Record<CardCheck["status"], string> = {
  pass: "text-[var(--teal)]",
  fail: "text-[var(--coral)]",
  not_applicable: "text-[var(--ink3)]",
};

interface GateHandlers {
  busy: boolean;
  onApprove: () => Promise<boolean>;
  onSendBack: (reason: G1Reason, feedback: string) => Promise<boolean>;
}

interface ProductionHandlers {
  busy: boolean;
  qaRunning: boolean;
  g2Busy: boolean;
  onRunQA: () => Promise<boolean>;
  onRepair: () => Promise<boolean>;
  onDismiss: (findingId: string, reason: string) => Promise<boolean>;
  onApproveG2: () => Promise<boolean>;
  onSendBackG2: (reason: G2Reason, feedback: string) => Promise<boolean>;
}

function ChecksPane({ detail, gate, production }: { detail: CardDetail; gate: GateHandlers; production: ProductionHandlers }) {
  const qaErrors = detail.qa && !detail.qa.stale ? (detail.qa.report?.error_count ?? 0) : 0;
  const failing = detail.checks.filter((c) => c.status === "fail").length + qaErrors;
  return (
    <Pane title="Checks and gate" chip={<span className={`chip ${failing ? "c" : "t"}`}>{failing ? `${failing} failing` : "all passing"}</span>}>
      <ul className="m-0 list-none p-0 text-[12.6px]" aria-label="Checks">
        {detail.checks.map((check) => (
          <li key={check.key} className="mb-[6px]" data-status={check.status}>
            <span className={`mr-[8px] font-mono ${CHECK_TONE[check.status]}`} aria-hidden>{CHECK_MARK[check.status]}</span>
            {check.label}
            {check.status === "not_applicable" ? <span className="sr-only"> (not applicable)</span> : null}
            {check.detail ? <div className="ml-[18px] text-[11.5px] text-[var(--ink3)]">{check.detail}</div> : null}
          </li>
        ))}
      </ul>
      <G1ReviewPanel detail={detail} busy={gate.busy} onApprove={gate.onApprove} onSendBack={gate.onSendBack} />
      <QAPanel
        detail={detail}
        running={production.qaRunning}
        busy={production.busy}
        onRun={production.onRunQA}
        onRepair={production.onRepair}
        onDismiss={production.onDismiss}
      />
      <G2ReviewPanel detail={detail} busy={production.g2Busy} onApprove={production.onApproveG2} onSendBack={production.onSendBackG2} />
      <div className="mt-[10px] border-t border-[var(--line2)] pt-[10px] text-[11.5px] text-[var(--ink3)]">
        State · {detail.card.state}
        {detail.bundle ? (
          <>
            <br />Bundle {detail.bundle.content_hash.slice(0, 10)} · {new Date(detail.bundle.built_at).toLocaleString("en-GB")}
          </>
        ) : null}
        <br />Publishing arrives in a later phase.
      </div>
    </Pane>
  );
}

export function CardDetailView({
  scope,
  cardId,
  backTo = "content-hub",
}: {
  scope: V3Scope;
  cardId: string;
  /** The Production module opens the same writer view; its back link returns there. */
  backTo?: "content-hub" | "production";
}) {
  const [detail, setDetail] = useState<CardDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [draft, setDraft] = useState<OutlineV3 | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<Busy | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState<string | null>(null);
  const [error, setError] = useState<{ message: string; issues: Issue[] } | null>(null);
  const seq = useRef(0);

  const apply = useCallback((next: CardDetail) => {
    setDetail(next);
    setDraft(next.outline);
    setDirty(false);
    setLoadError(null);
  }, []);

  useEffect(() => {
    const current = ++seq.current;
    V3API.contentHub.card(scope, cardId).then(
      (next) => current === seq.current && apply(next),
      (cause: unknown) => {
        if (current !== seq.current) return;
        setLoadError(
          cause instanceof ApiError && cause.status === 404
            ? "This card was not found in this project."
            : cause instanceof ApiError && cause.status === 403
              ? "You do not have access to this card."
              : describe(cause, "The card could not be loaded.").message,
        );
      },
    );
  }, [scope, cardId, apply]);

  const reload = useCallback(async () => {
    apply(await V3API.contentHub.card(scope, cardId));
  }, [apply, scope, cardId]);

  const run = async (kind: Busy, action: () => Promise<void>, fallback: string): Promise<boolean> => {
    setBusy(kind);
    setError(null);
    setNotice(null);
    try {
      await action();
      return true;
    } catch (cause) {
      setError(describe(cause, fallback));
      return false;
    } finally {
      setBusy(null);
    }
  };

  const pages = useMemo<PageOption[]>(
    () =>
      (detail?.context.references.existing_pages.pages ?? [])
        .filter((p): p is typeof p & { page_id: string } => Boolean(p.page_id))
        .map((p) => ({ page_id: p.page_id, url: p.url, title: p.title })),
    [detail],
  );

  if (loadError) {
    return (
      <div>
        <BackLink projectId={scope.projectId} to={backTo} />
        <p role="alert" className="mt-[12px] text-sm text-[var(--coral)]">{loadError}</p>
      </div>
    );
  }
  if (!detail) {
    return <p aria-label="Loading the card" className="h-[320px] animate-pulse rounded-[8px] bg-[#EDF0EF]" />;
  }

  const { card, actions, context, review } = detail;
  const modelOptions = detail.generation?.options ?? [];
  const models = modelOptions.map((o) => o.model);
  const chosenModel = model && models.includes(model) ? model : (detail.generation?.default_model ?? models[0]);
  const providers = [...new Set(modelOptions.map((o) => o.provider))];
  const gate: GateHandlers = {
    busy: busy === "approve" || busy === "sendback",
    onApprove: () =>
      run("approve", async () => {
        await V3API.contentHub.approveG1(scope, cardId, card.revision);
        await reload();
        setNotice("Outline approved at G1. Drafting can start.");
      }, "The outline could not be approved."),
    onSendBack: (reason, feedback) =>
      run("sendback", async () => {
        await V3API.contentHub.sendBackG1(scope, cardId, card.revision, reason, feedback);
        await reload();
        setNotice("Outline sent back with feedback.");
      }, "The outline could not be sent back."),
  };
  const lastSendBack = review.last_decision?.action === "send_back" ? review.last_decision : null;
  const failAndReload = async <T,>(action: () => Promise<T>): Promise<T> => {
    try {
      return await action();
    } catch (cause) {
      // Failed runs are recorded server-side; show them alongside the error.
      await reload().catch(() => undefined);
      throw cause;
    }
  };
  const production: ProductionHandlers = {
    busy: busy !== null,
    qaRunning: busy === "qa",
    g2Busy: busy === "g2approve" || busy === "g2sendback",
    onRunQA: () =>
      run("qa", async () => {
        const result = await failAndReload(() => V3API.contentHub.runQA(scope, cardId, card.revision, chosenModel));
        await reload();
        setNotice(
          result.report.status === "passed"
            ? `QA passed with ${result.report.warning_count} warning(s).`
            : `QA failed: ${result.report.error_count} error(s).`,
        );
      }, "QA could not run."),
    onRepair: () =>
      run("repair", async () => {
        const result = await failAndReload(() => V3API.contentHub.repairDraft(scope, cardId, card.revision, chosenModel));
        await reload();
        setNotice(`Draft v${result.draft.version} repaired. Run QA again.`);
      }, "The draft could not be repaired."),
    onDismiss: (findingId, reason) =>
      run("dismiss", async () => {
        await V3API.contentHub.dismissWarning(scope, cardId, card.revision, findingId, reason);
        await reload();
        setNotice("Warning dismissed.");
      }, "The warning could not be dismissed."),
    onApproveG2: () =>
      run("g2approve", async () => {
        await V3API.contentHub.approveG2(scope, cardId, card.revision);
        await reload();
        setNotice("Draft approved at G2.");
      }, "The draft could not be approved."),
    onSendBackG2: (reason, feedback) =>
      run("g2sendback", async () => {
        await V3API.contentHub.sendBackG2(scope, cardId, card.revision, reason, feedback);
        await reload();
        setNotice("Draft sent back to drafting with feedback.");
      }, "The draft could not be sent back."),
  };
  const onRegenerate = async (sectionId: string, feedback: string) => {
    setRegenerating(sectionId);
    try {
      return await run("regen", async () => {
        const result = await failAndReload(() =>
          V3API.contentHub.regenerateSection(scope, cardId, sectionId, card.revision, feedback, chosenModel),
        );
        await reload();
        setNotice(`Section regenerated (draft v${result.draft.version}). Run QA again.`);
      }, "The section could not be regenerated.");
    } finally {
      setRegenerating(null);
    }
  };
  const promptId = context.demand.find((d) => d.role === "prompt")?.id ?? null;
  const primary = context.demand.find((d) => d.role === "primary") ?? context.demand.find((d) => d.role === "prompt");

  return (
    <section className="animate-in fade-in duration-150">
      <BackLink projectId={scope.projectId} to={backTo} />
      <div className="mt-[10px] mb-[13px] flex flex-wrap items-center gap-[10px] rounded-[8px] border border-[var(--line)] bg-white px-[14px] py-[11px]">
        <div className="min-w-[220px]">
          <h1 className="m-0 font-serif text-[21px] font-medium tracking-tight">{card.title || "Untitled card"}</h1>
          <div className="text-[11.5px] text-[var(--ink3)]">
            {card.kind} · {card.area?.name ?? "No area"} · {card.market ?? "no market"}
          </div>
        </div>
        <span className="chip c" data-testid="card-state">{card.state}</span>
        <G1StatusChip status={review.status} />
        {PRODUCTION_STATES.includes(card.state) ? <QAChip state={qaChipState(detail, busy === "qa")} /> : null}
        {detail.g2 && detail.g2.status !== "not_ready" ? <G2StatusChip status={detail.g2.status} /> : null}
        {card.argument ? <span className="chip t">{card.argument.name}</span> : null}
        {primary ? (
          <span className="chip r">
            {primary.text}
            {primary.volume !== null ? ` · ${primary.volume}` : ""}
          </span>
        ) : null}
        {card.owner ? <span className="chip r">owner {card.owner.name}</span> : null}
        {card.due ? <span className="chip r">due {card.due}</span> : null}
        <span className="ml-auto flex gap-[6px]">
          <button type="button" className={btn} disabled={!actions.can_build_bundle || busy !== null}
            onClick={() => run("bundle", async () => {
              const result = await V3API.contentHub.buildBundle(scope, cardId, card.revision);
              await reload();
              setNotice(result.reused ? "Bundle is current; reused." : "Bundle built.");
            }, "The bundle could not be built.")}>
            {busy === "bundle" ? "Building…" : detail.bundle ? "Rebuild bundle" : "Build bundle"}
          </button>
        </span>
      </div>

      {notice ? <p role="status" className="mb-[10px] text-[12.6px] text-[var(--teal)]">{notice}</p> : null}
      {error ? (
        <div role="alert" className="mb-[10px] text-[12.6px] text-[var(--coral)]">
          {error.message}
          {error.message === CONFLICT_MESSAGE ? (
            <button type="button" className={`${btn} ml-[8px]`} onClick={() => run("save", reload, "Reload failed.")}>Reload</button>
          ) : null}
          {error.issues.length ? (
            <ul className="m-[4px_0_0] pl-[18px]">
              {error.issues.map((issue, i) => (
                <li key={i}>{issue.section_id ? `${issue.section_id}: ` : ""}{issue.message}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-[13px] lg:grid-cols-[minmax(0,260px)_minmax(0,1.6fr)_minmax(0,300px)]">
        <ContextPane detail={detail} />

        <section aria-label="Document" className="min-w-0 rounded-[8px] border border-[var(--line)] bg-white">
          <Tabs defaultValue={PRODUCTION_STATES.includes(card.state) ? "draft" : "outline"}>
            <header className="flex flex-wrap items-center gap-[8px] border-b border-[var(--line2)] px-[13px] py-[6px]">
              <TabsList variant="line" className="justify-start rounded-none bg-transparent p-0">
                <TabsTrigger value="outline">Outline</TabsTrigger>
                <TabsTrigger value="draft">Draft</TabsTrigger>
              </TabsList>
              <span className="ml-auto flex items-center gap-[6px]">
                {models.length > 1 &&
                (actions.can_generate_outline || card.state === "drafting" || actions.can_run_qa || actions.can_repair || actions.can_regenerate_section) ? (
                  <label className="flex items-center gap-[5px] text-[11.5px] text-[var(--ink3)]">
                    Model
                    <select
                      aria-label="Generation model"
                      className="rounded-[5px] border border-[var(--line)] bg-white px-[6px] py-[3px] text-[12.5px] text-[#12171A]"
                      value={chosenModel}
                      disabled={busy !== null}
                      onChange={(event) => setModel(event.target.value)}
                    >
                      {providers.map((provider) => (
                        <optgroup key={provider} label={PROVIDER_LABEL[provider] ?? provider}>
                          {modelOptions
                            .filter((o) => o.provider === provider)
                            .map((o) => (
                              <option key={o.model} value={o.model}>
                                {o.model}
                              </option>
                            ))}
                        </optgroup>
                      ))}
                    </select>
                  </label>
                ) : null}
                {!PRODUCTION_STATES.includes(card.state) ? (
                <>
                <button type="button" className={btn} disabled={!actions.can_generate_outline || busy !== null}
                  title={actions.can_generate_outline ? "" : "Needs a current bundle"}
                  onClick={() => run("generate", async () => {
                    const proposal = await V3API.contentHub.generateOutline(scope, cardId, chosenModel);
                    setDraft(proposal.outline);
                    setDirty(true);
                    setNotice(`Proposal from ${proposal.model} (${proposal.prompt_version}). Review, edit and save.`);
                  }, "The outline could not be generated.")}>
                  {busy === "generate" ? "Generating…" : "Generate outline"}
                </button>
                <button type="button" className={btnPrimary}
                  disabled={!actions.can_save_outline || !draft || !dirty || busy !== null}
                  onClick={() => draft && run("save", async () => {
                    await V3API.contentHub.saveOutline(scope, cardId, draft, card.revision);
                    await reload();
                    setNotice("Outline saved.");
                  }, "The outline could not be saved.")}>
                  {busy === "save" ? "Saving…" : "Save outline"}
                </button>
                </>
                ) : null}
                {card.state === "drafting" ? (
                  <button type="button" className={btnPrimary} disabled={!actions.can_generate_draft || busy !== null}
                    title={actions.can_generate_draft ? "" : "Needs a current bundle"}
                    onClick={() => run("draft", async () => {
                      try {
                        const result = await V3API.contentHub.generateDraft(scope, cardId, card.revision, chosenModel);
                        await reload();
                        setNotice(`Draft v${result.draft.version} stored from ${result.draft.model} (${result.draft.prompt_version}).`);
                      } catch (cause) {
                        // The failed run is recorded server-side; show it alongside the error.
                        await reload().catch(() => undefined);
                        throw cause;
                      }
                    }, "The draft could not be generated.")}>
                    {busy === "draft" ? "Generating draft…" : detail.draft ? "Regenerate draft" : "Generate draft"}
                  </button>
                ) : null}
              </span>
            </header>
            <TabsContent value="outline" className="p-[13px]">
              {review.status === "approved" && review.last_decision?.action === "approve" ? (
                <div className="mb-[10px] rounded-[6px] bg-[#E6F2F1] px-[9px] py-[7px] text-[12.4px]" role="note">
                  <b>Approved at G1 on {formatWhen(review.last_decision.decided_at)}.</b> The draft may not introduce a claim absent from
                  this outline.
                </div>
              ) : null}
              {card.state === "outlined" && lastSendBack ? (
                <div className="mb-[10px] rounded-[6px] bg-[#FBEFEC] px-[9px] py-[7px] text-[12.4px]" role="note" data-testid="sent-back-banner">
                  <div className="text-[11.5px] text-[var(--ink3)]">{decisionLine(lastSendBack)}</div>
                  <p className="m-[3px_0_0] whitespace-pre-wrap">{lastSendBack.feedback}</p>
                </div>
              ) : null}
              {detail.outline_unreadable ? (
                <p className="mb-[10px] text-[12.6px] text-[var(--coral)]">The stored outline no longer matches the V3 outline schema.</p>
              ) : null}
              {draft ? (
                <OutlineEditor
                  outline={draft}
                  onChange={(next) => {
                    setDraft(next);
                    setDirty(true);
                  }}
                  claims={detail.claim_options}
                  demand={context.demand}
                  pages={pages}
                  disabled={!actions.can_save_outline || busy !== null}
                />
              ) : (
                <div className="text-[12.8px] text-[#5C666C]">
                  <p className="m-0">No outline yet.</p>
                  {actions.can_save_outline ? (
                    <button type="button" className={`${btn} mt-[8px]`}
                      onClick={() => {
                        setDraft(blankOutline(card.title, context.card.primary_mode, promptId));
                        setDirty(true);
                      }}>
                      Start a blank outline
                    </button>
                  ) : (
                    <p className="m-[4px_0_0] text-[var(--ink3)]">Build the bundle to start the outline.</p>
                  )}
                </div>
              )}
            </TabsContent>
            <TabsContent value="draft" className="p-[13px]">
              {busy === "draft" ? (
                <p aria-busy="true" className="m-[0_0_10px] text-[12.8px] text-[var(--teal)]">
                  Generating the draft from the stored bundle and the approved outline…
                </p>
              ) : null}
              {card.state === "drafting" || detail.draft ? (
                <>
                  {card.state === "drafting" && !actions.can_generate_draft ? (
                    <p className="m-[0_0_10px] text-[12.6px] text-[var(--coral)]">
                      The bundle is out of date. Rebuild it before drafting.
                    </p>
                  ) : null}
                  <DraftView
                    draft={detail.draft}
                    unreadable={detail.draft_unreadable}
                    lastRun={detail.last_draft_run}
                    claims={detail.claim_options}
                    findings={detail.qa && !detail.qa.stale ? (detail.qa.report?.findings ?? []) : []}
                    canRegenerate={actions.can_regenerate_section && busy === null}
                    regenerating={regenerating}
                    onRegenerate={onRegenerate}
                  />
                </>
              ) : (
                <p className="m-0 text-[12.8px] text-[var(--ink3)]">Drafting starts after the outline passes G1.</p>
              )}
            </TabsContent>
          </Tabs>
        </section>

        <ChecksPane detail={detail} gate={gate} production={production} />
      </div>
    </section>
  );
}

function BackLink({ projectId, to }: { projectId: string; to: "content-hub" | "production" }) {
  const production = to === "production";
  return (
    <Link
      href={`/projects/${projectId}/v3/${production ? "production" : "content-hub"}`}
      className="text-[12.5px] text-[#5C666C] hover:text-[#12171A]"
    >
      ← Back to {production ? "Production" : "Content Hub"}
    </Link>
  );
}
