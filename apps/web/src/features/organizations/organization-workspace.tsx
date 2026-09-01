"use client";

import { Building2, Plus, ArrowRight } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Input } from "@/components/input";
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
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section>
        <div className="grid gap-4 sm:grid-cols-2">
          {items.map((organization) => (
            <Link href={`/projects?organization_id=${organization.id}`} key={organization.id}>
              <Card className="group h-full p-5 transition hover:-translate-y-0.5 hover:border-[#b8b2ff] hover:shadow-md">
                <div className="flex items-start justify-between gap-4">
                  <span className="grid size-11 place-items-center rounded-xl bg-[var(--accent-soft)] text-[var(--accent)]">
                    <Building2 aria-hidden size={20} />
                  </span>
                  <ArrowRight aria-hidden className="text-[var(--muted)] transition group-hover:translate-x-1" size={18} />
                </div>
                <h2 className="mb-1 mt-7 text-lg font-bold tracking-[-0.02em]">{organization.name}</h2>
                <p className="m-0 text-sm text-[var(--muted)]">/{organization.slug}</p>
              </Card>
            </Link>
          ))}
          {!items.length ? (
            <Card className="grid min-h-48 place-items-center border-dashed p-6 text-center sm:col-span-2">
              <div>
                <Building2 aria-hidden className="mx-auto text-[var(--muted)]" />
                <p className="mb-1 mt-4 font-semibold">No organization yet</p>
                <p className="m-0 text-sm text-[var(--muted)]">Create the tenant boundary for your first workspace.</p>
              </div>
            </Card>
          ) : null}
        </div>
      </section>
      <Card className="h-fit p-6 shadow-[var(--shadow)]">
        <span className="inline-flex items-center gap-2 text-sm font-bold"><Plus aria-hidden size={16} /> New organization</span>
        <p className="mb-5 mt-2 text-sm leading-6 text-[var(--muted)]">Organizations isolate members, projects, websites, and every future content record.</p>
        <form className="grid gap-4" onSubmit={createOrganization}>
          <Input label="Organization name" name="name" onChange={(event) => setName(event.target.value)} placeholder="Acme Content Studio" required value={name} />
          {error ? <p className="m-0 text-sm text-[var(--danger)]" role="alert">{error}</p> : null}
          <Button disabled={pending || name.trim().length < 2} type="submit">{pending ? "Creating…" : "Create organization"}</Button>
        </form>
      </Card>
    </div>
  );
}
