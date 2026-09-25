"use client";

import { useMemo } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { V3Scope } from "@/lib/v3-api";

import { PlanBoard } from "./plan-board";

export function ContentHub({ organizationId, projectId }: { organizationId: string; projectId: string }) {
  const scope = useMemo<V3Scope>(() => ({ organizationId, projectId }), [organizationId, projectId]);
  return (
    <section className="animate-in fade-in duration-150">
      <div className="min-w-[280px]">
        <div className="mb-[6px] text-[11.5px] text-[#8A949A]">Module · planned</div>
        <h1 className="m-0 font-serif text-[25px] font-medium tracking-tight text-[#12171A]">Content Hub</h1>
        <p className="m-[5px_0_0] max-w-[74ch] text-[13.4px] text-[#5C666C]">
          One board whose columns are the card state machine and nothing else. Cards move by passing gates in Production;
          here you only plan them and set their priority.
        </p>
      </div>
      <Tabs defaultValue="board" className="mt-[18px]">
        <TabsList variant="line" className="w-full justify-start rounded-none border-b border-[#D6DBD9] bg-transparent p-0">
          <TabsTrigger value="board">Plan board</TabsTrigger>
          {/* §5.3 Dashboard needs data sources that do not exist yet; shown, not faked. */}
          <TabsTrigger value="dashboard" disabled title="Not available yet">
            Dashboard
          </TabsTrigger>
        </TabsList>
        <TabsContent value="board" className="mt-[18px]">
          <PlanBoard scope={scope} />
        </TabsContent>
      </Tabs>
    </section>
  );
}
