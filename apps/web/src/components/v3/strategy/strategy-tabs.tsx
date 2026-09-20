"use client";

import { useMemo } from "react";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { V3Scope } from "@/lib/v3-api";

import { CanvasTab } from "./canvas-tab";
import { DemandTab } from "./demand-tab";

export function StrategyTabs({
  organizationId,
  projectId,
  defaultTab = "canvas",
}: {
  organizationId: string;
  projectId: string;
  defaultTab?: "canvas" | "demand";
}) {
  const scope = useMemo<V3Scope>(
    () => ({ organizationId, projectId }),
    [organizationId, projectId],
  );
  return (
    <section className="animate-in fade-in duration-150">
      <div className="flex flex-wrap items-start gap-[16px]">
        <div className="min-w-[280px] flex-1">
          <div className="mb-[6px] text-[11.5px] text-[#8A949A]">Module · authored</div>
          <h1 className="m-0 font-serif text-[25px] font-medium tracking-tight text-[#12171A]">Strategy</h1>
          <p className="m-[5px_0_0] max-w-[74ch] text-[13.4px] text-[#5C666C]">
            The canvas is the source of every claim a page may assert. Demand hangs off the product tree and carries an argument tag.
          </p>
        </div>
      </div>
      <Tabs defaultValue={defaultTab} className="mt-[18px]">
        <TabsList variant="line" className="w-full justify-start rounded-none border-b border-[#D6DBD9] bg-transparent p-0">
          <TabsTrigger value="canvas">Canvas</TabsTrigger>
          <TabsTrigger value="demand">Demand</TabsTrigger>
          <TabsTrigger value="brand" disabled>Brand kit</TabsTrigger>
          <TabsTrigger value="map" disabled>Map</TabsTrigger>
        </TabsList>
        <TabsContent value="canvas" className="mt-[18px]"><CanvasTab scope={scope} /></TabsContent>
        <TabsContent value="demand" className="mt-[18px]"><DemandTab scope={scope} /></TabsContent>
      </Tabs>
    </section>
  );
}
