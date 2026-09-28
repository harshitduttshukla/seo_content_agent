"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { v3 } from "@/components/v3/v3-top-bar";
import { ApiError, apiRequest, idempotencyKey } from "@/lib/client-api";
import type { Organization } from "@/lib/api-types";

export function OrganizationWorkspace({ initialItems }: { initialItems: Organization[] }) {
  const [items, setItems] = useState(initialItems);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function createOrganization(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const created = await apiRequest<Organization>("/organizations", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey("organization") },
        body: JSON.stringify({ name }),
      });
      setItems((current) => [created, ...current]);
      setName("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Organization could not be created.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid items-start gap-[16px] lg:grid-cols-[minmax(0,1fr)_320px]">
      <section aria-label="Organizations" className="grid gap-[10px] sm:grid-cols-2">
        {items.map((organization) => (
          <Link href={`/projects?organization_id=${organization.id}`} key={organization.id} className={v3.cardLink}>
            <div className="flex items-center justify-between gap-[10px]">
              <h2 className="m-0 font-serif text-[19px] font-medium text-[#12171A]">{organization.name}</h2>
              <ArrowRight aria-hidden size={16} className="flex-none text-[#8A949A] transition-transform group-hover:translate-x-0.5 group-hover:text-[#15706A]" />
            </div>
            <p className="m-[4px_0_0] font-mono text-[11.5px] text-[#8A949A]">/{organization.slug}</p>
          </Link>
        ))}
        {!items.length ? (
          <div className="rounded-[8px] border border-dashed border-[#D6DBD9] bg-[#FAFBFA] p-[22px] text-center sm:col-span-2">
            <p className="m-0 text-[13.3px] font-medium text-[#12171A]">No organization yet</p>
            <p className="m-[4px_0_0] text-[12.6px] text-[#5C666C]">Create one to hold your projects and team.</p>
          </div>
        ) : null}
      </section>

      <section aria-label="New organization" className={`${v3.card} p-[16px_18px]`}>
        <h2 className="m-0 text-[13.3px] font-medium text-[#12171A]">New organization</h2>
        <p className="m-[4px_0_14px] text-[12.6px] leading-[1.5] text-[#5C666C]">
          Each organization keeps its members, projects and content separate from every other one.
        </p>
        <form className="grid gap-[12px]" onSubmit={createOrganization}>
          <label className={v3.label}>
            Organization name
            <input
              id="organization-name"
              name="name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Acme Content Studio"
              className={v3.field}
            />
          </label>
          {error ? <p role="alert" className="m-0 text-[12.6px] text-[#B9463A]">{error}</p> : null}
          <button type="submit" disabled={pending || name.trim().length < 2} className={v3.primary}>
            {pending ? "Creating…" : "Create organization"}
          </button>
        </form>
      </section>
    </div>
  );
}
