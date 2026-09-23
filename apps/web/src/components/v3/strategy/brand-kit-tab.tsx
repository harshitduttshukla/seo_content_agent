"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Area, BrandKitInput, SocialProofInput, VoiceSnippetInput } from "@/lib/api-types";
import { V3API, type V3Scope } from "@/lib/v3-api";

const emptyKit: BrandKitInput = {
  spelling: "", banned_words: [], style: "", vocabulary: "", tone_profile: "", profile_provisional: true,
};

function commaValues(value: string): string[] {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function Chip({ children, coral = false }: { children: React.ReactNode; coral?: boolean }) {
  return <span className={coral ? "rounded-full border border-[#F0D2CC] bg-[#FBEBE8] px-2 py-0.5 text-[10.5px] font-medium text-[#B9463A]" : "rounded-full border border-[#C4DEDA] bg-[#E1EFED] px-2 py-0.5 text-[10.5px] font-medium text-[#15706A]"}>{children}</span>;
}

export function BrandKitTab({ scope }: { scope: V3Scope }) {
  const [kit, setKit] = useState<BrandKitInput>(emptyKit);
  const [voice, setVoice] = useState<VoiceSnippetInput>({ source_type: "call", source_name: "", captured_on: "", content: "", area_id: null });
  const [proof, setProof] = useState<SocialProofInput>({ label: "", proof_type: "case study", area_ids: [], markets: [], approved: true });
  const [snippets, setSnippets] = useState<Awaited<ReturnType<typeof V3API.brandKit.get>>["voice_snippets"]>([]);
  const [proofs, setProofs] = useState<Awaited<ReturnType<typeof V3API.brandKit.get>>["social_proofs"]>([]);
  const [areas, setAreas] = useState<Area[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [result, projectAreas] = await Promise.all([
        V3API.brandKit.get(scope),
        V3API.areas.list(scope),
      ]);
      setKit(result.brand_kit ? { spelling: result.brand_kit.spelling, banned_words: result.brand_kit.banned_words, style: result.brand_kit.style, vocabulary: result.brand_kit.vocabulary, tone_profile: result.brand_kit.tone_profile, profile_provisional: result.brand_kit.profile_provisional } : emptyKit);
      setSnippets(result.voice_snippets); setProofs(result.social_proofs);
      setAreas(projectAreas);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Brand Kit could not be loaded."); }
    finally { setLoading(false); }
  }, [scope]);
  useEffect(() => { void load(); }, [load]);

  async function saveKit(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setError(null);
    try { await V3API.brandKit.save(scope, kit); } catch (cause) { setError(cause instanceof Error ? cause.message : "Brand Kit could not be saved."); }
    finally { setSaving(false); }
  }
  async function addVoice(event: React.FormEvent) {
    event.preventDefault(); setError(null);
    try { const item = await V3API.brandKit.addVoiceSnippet(scope, voice); setSnippets((all) => [item, ...all]); setVoice({ source_type: "call", source_name: "", captured_on: "", content: "", area_id: null }); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Voice sample could not be added."); }
  }
  async function addProof(event: React.FormEvent) {
    event.preventDefault(); setError(null);
    try { const item = await V3API.brandKit.addSocialProof(scope, proof); setProofs((all) => [item, ...all]); setProof({ label: "", proof_type: "case study", area_ids: [], markets: [], approved: true }); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Social proof could not be added."); }
  }
  if (loading) return <p className="text-sm text-[#5C666C]">Loading Brand kit…</p>;
  return <div className="grid gap-[14px] xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
    <div className="space-y-[14px]">
      <form onSubmit={saveKit} className="rounded-[8px] border border-[#D6DBD9] bg-white">
        <div className="flex items-center justify-between border-b border-[#E7EAE9] px-[15px] py-[11px]"><h2 className="font-serif text-[18px] text-[#12171A]">Tone</h2><Chip coral={kit.profile_provisional}>profile {kit.profile_provisional ? "provisional" : "established"}</Chip></div>
        <div className="space-y-3 p-[15px] text-[13px]">
          <label className="block">Spelling<Input value={kit.spelling} onChange={(e) => setKit({ ...kit, spelling: e.target.value })} placeholder="en-GB · demand strings exempt" className="mt-1 border-[#D6DBD9] text-[13px]" /></label>
          <label className="block">Banned words<Input value={kit.banned_words.join(", ")} onChange={(e) => setKit({ ...kit, banned_words: commaValues(e.target.value) })} placeholder="seamless, unlock, revolutionary" className="mt-1 border-[#D6DBD9] text-[13px]" /></label>
          <label className="block">Style<textarea value={kit.style} onChange={(e) => setKit({ ...kit, style: e.target.value })} className="mt-1 min-h-16 w-full rounded-lg border border-[#D6DBD9] p-2 text-[13px]" placeholder="Operator to operator. Short declaratives. No superlatives." /></label>
          <label className="block">Vocabulary<textarea value={kit.vocabulary} onChange={(e) => setKit({ ...kit, vocabulary: e.target.value })} className="mt-1 min-h-16 w-full rounded-lg border border-[#D6DBD9] p-2 text-[13px]" placeholder='"landed cost" in buyer-facing copy' /></label>
          <label className="block">Tone profile<textarea value={kit.tone_profile} onChange={(e) => setKit({ ...kit, tone_profile: e.target.value })} className="mt-1 min-h-16 w-full rounded-lg border border-[#D6DBD9] p-2 text-[13px]" placeholder="A concise description derived from voice samples." /></label>
          <label className="flex items-center gap-2 text-[12px]"><input type="checkbox" checked={kit.profile_provisional} onChange={(e) => setKit({ ...kit, profile_provisional: e.target.checked })} /> Profile is provisional</label>
          <Button type="submit" size="sm" disabled={saving} className="bg-[#15706A]">{saving ? "Saving…" : "Save tone"}</Button>
          <p className="m-0 text-[11px] text-[#8A949A]">Profile is derived from the canvas while the corpus is below 10 sources. It re-derives automatically past that.</p>
        </div>
      </form>
      <section className="rounded-[8px] border border-[#D6DBD9] bg-white"><div className="flex items-center justify-between border-b border-[#E7EAE9] px-[15px] py-[11px]"><h2 className="font-serif text-[18px]">Voice corpus</h2><Chip>{snippets.length} sources</Chip></div><div className="p-[15px]">{snippets.length ? <div className="space-y-2">{snippets.map((item) => <div key={item.id} className="border-b border-[#E7EAE9] pb-2 last:border-0"><p className="m-0 text-[13px] text-[#12171A]">“{item.content}”</p><p className="m-1 text-[11px] text-[#8A949A]">{item.source_type} · {item.source_name} · {item.captured_on}</p></div>)}</div> : <p className="text-[12px] text-[#8A949A]">Add source material to establish the voice profile.</p>}<form onSubmit={addVoice} className="mt-3 grid gap-2"><Input required value={voice.source_name} onChange={(e) => setVoice({ ...voice, source_name: e.target.value })} placeholder="Source name" /><div className="grid grid-cols-2 gap-2"><Input required value={voice.source_type} onChange={(e) => setVoice({ ...voice, source_type: e.target.value })} placeholder="Source type" /><Input required type="date" value={voice.captured_on} onChange={(e) => setVoice({ ...voice, captured_on: e.target.value })} /></div><select aria-label="Voice area" value={voice.area_id ?? ""} onChange={(e) => setVoice({ ...voice, area_id: e.target.value || null })} className="h-8 rounded-lg border border-[#D6DBD9] px-2 text-[13px]"><option value="">All areas</option>{areas.map((area) => <option key={area.id} value={area.id}>{area.name}</option>)}</select><textarea required value={voice.content} onChange={(e) => setVoice({ ...voice, content: e.target.value })} className="min-h-16 rounded-lg border border-[#D6DBD9] p-2 text-[13px]" placeholder="Voice sample" /><Button type="submit" variant="outline" size="sm">Add source</Button></form></div></section>
    </div>
    <section className="h-fit rounded-[8px] border border-[#D6DBD9] bg-white"><div className="flex items-center justify-between border-b border-[#E7EAE9] px-[15px] py-[11px]"><div className="flex items-center gap-2"><h2 className="font-serif text-[18px]">Social proof</h2><Chip>{proofs.length}</Chip></div></div><div className="p-[15px]"><div className="space-y-2">{proofs.map((item) => <div key={item.id} className="grid grid-cols-[1fr_auto] gap-2 border-b border-[#E7EAE9] pb-2 last:border-0"><div><p className="m-0 text-[13px] text-[#12171A]">{item.label}</p><p className="m-1 text-[11px] text-[#8A949A]">{item.proof_type} · {item.markets.join(", ") || "all markets"} · {item.area_ids.length ? `${item.area_ids.length} areas` : "all areas"}</p></div><Chip coral={!item.approved}>{item.approved ? "approved" : "not approved"}</Chip></div>)}</div><form onSubmit={addProof} className="mt-3 grid gap-2"><Input required value={proof.label} onChange={(e) => setProof({ ...proof, label: e.target.value })} placeholder="Proof, customer, or statistic" /><div className="grid grid-cols-2 gap-2"><Input required value={proof.proof_type} onChange={(e) => setProof({ ...proof, proof_type: e.target.value })} placeholder="Type" /><Input value={proof.markets.join(", ")} onChange={(e) => setProof({ ...proof, markets: commaValues(e.target.value) })} placeholder="Markets (comma separated)" /></div><select multiple aria-label="Proof areas" value={proof.area_ids} onChange={(e) => setProof({ ...proof, area_ids: Array.from(e.target.selectedOptions, (option) => option.value) })} className="min-h-20 rounded-lg border border-[#D6DBD9] p-2 text-[13px]">{areas.map((area) => <option key={area.id} value={area.id}>{area.name}</option>)}</select><label className="flex items-center gap-2 text-[12px]"><input type="checkbox" checked={proof.approved} onChange={(e) => setProof({ ...proof, approved: e.target.checked })} /> Approved for use</label><Button type="submit" size="sm" className="bg-[#15706A]">+ add</Button></form><p className="mt-3 text-[11px] text-[#8A949A]">Competitor edge stays in the alternative canvas anchor and workspace configuration.</p></div></section>
    {error ? <p role="alert" className="xl:col-span-2 text-sm text-[#B9463A]">{error}</p> : null}
  </div>;
}
