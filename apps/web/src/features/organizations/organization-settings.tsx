"use client";

import {
  ArrowLeft,
  Building2,
  CheckCircle2,
  Plus,
  Save,
  Shield,
  UserPlus,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button } from "@/components/button";
import { Card } from "@/components/card";
import { Dropdown } from "@/components/dropdown";
import { Input } from "@/components/input";
import { Modal } from "@/components/modal";
import { Table, TableCell, TableHead } from "@/components/table";
import { Toast } from "@/components/toast";
import { ApiError, apiRequest } from "@/lib/client-api";
import type { Organization } from "@/lib/api-types";

export type OrganizationMember = {
  id: string;
  user_id: string;
  email: string;
  display_name: string;
  role: "admin" | "seo_manager" | "content_manager" | "writer" | "editor" | "viewer";
  status: "active" | "suspended";
  joined_at: string;
};

const ROLES = [
  { value: "admin", label: "Admin", desc: "Full access to all organization projects, settings, and team" },
  { value: "seo_manager", label: "SEO Manager", desc: "Strategy, keywords, rules, and technical SEO" },
  { value: "content_manager", label: "Content Manager", desc: "Content calendar, briefs, and cluster assignment" },
  { value: "editor", label: "Editor", desc: "Content review, publishing governance, and AI proposals" },
  { value: "writer", label: "Writer", desc: "Brief drafting, article writing, and suggestion preview" },
  { value: "viewer", label: "Viewer", desc: "Read-only workspace and preview access" },
] as const;

export function OrganizationSettings({
  organization: initialOrg,
  initialMembers,
}: {
  organization: Organization;
  initialMembers: OrganizationMember[];
}) {
  const router = useRouter();
  const [org, setOrg] = useState<Organization>(initialOrg);
  const [name, setName] = useState(initialOrg.name);
  const [slug, setSlug] = useState(initialOrg.slug);
  const [status, setStatus] = useState<string>(initialOrg.status);
  const [members, setMembers] = useState<OrganizationMember[]>(initialMembers);

  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Add member modal
  const [showAddMember, setShowAddMember] = useState(false);
  const [addUserId, setAddUserId] = useState("");
  const [addRole, setAddRole] = useState<OrganizationMember["role"]>("writer");
  const [addMemberPending, setAddMemberPending] = useState(false);
  const [addMemberError, setAddMemberError] = useState("");

  function showToast(msg: string) {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  }

  async function handleUpdateOrg(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const updated = await apiRequest<Organization>(`/organizations/${org.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: name.trim(),
          slug: slug.trim(),
          status,
          revision: org.revision,
        }),
      });
      setOrg(updated);
      setName(updated.name);
      setSlug(updated.slug);
      setStatus(updated.status);
      showToast("Organization settings saved.");
      router.refresh();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Failed to update organization.");
    } finally {
      setPending(false);
    }
  }

  async function handleAddMember(event: FormEvent) {
    event.preventDefault();
    setAddMemberPending(true);
    setAddMemberError("");
    try {
      const created = await apiRequest<OrganizationMember>(`/organizations/${org.id}/members`, {
        method: "POST",
        body: JSON.stringify({
          user_id: addUserId.trim(),
          role: addRole,
        }),
      });
      setMembers((curr) => [...curr, created]);
      setShowAddMember(false);
      setAddUserId("");
      setAddRole("writer");
      showToast("Team member added successfully.");
    } catch (caught) {
      setAddMemberError(caught instanceof ApiError ? caught.message : "Failed to add member.");
    } finally {
      setAddMemberPending(false);
    }
  }

  async function handleUpdateMemberRole(userId: string, newRole: OrganizationMember["role"], currentStatus: string) {
    try {
      const updated = await apiRequest<OrganizationMember>(`/organizations/${org.id}/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({
          role: newRole,
          status: currentStatus,
        }),
      });
      setMembers((curr) => curr.map((m) => (m.user_id === userId ? updated : m)));
      showToast("Member role updated.");
    } catch (caught) {
      showToast(caught instanceof ApiError ? caught.message : "Failed to update member role.");
    }
  }

  return (
    <div className="mx-auto grid max-w-5xl gap-8 p-4 sm:p-8">
      <div className="flex items-center justify-between">
        <div>
          <Link
            className="mb-2 inline-flex items-center gap-1.5 text-xs font-bold text-[var(--muted)] hover:text-[var(--ink)]"
            href={`/projects?organization_id=${org.id}`}
          >
            <ArrowLeft aria-hidden size={14} /> Back to projects
          </Link>
          <h1 className="mb-0 text-2xl font-bold tracking-tight">Organization Settings</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Manage top-level tenant boundaries, organization identity, and role-based team permissions.
          </p>
        </div>
        <span className="grid size-12 place-items-center rounded-2xl bg-[var(--accent-soft)] text-[var(--accent)]">
          <Building2 aria-hidden size={24} />
        </span>
      </div>

      {/* General Settings */}
      <Card className="p-6">
        <h2 className="mb-1 text-lg font-bold">Workspace Profile</h2>
        <p className="mb-5 text-xs text-[var(--muted)]">
          Update the organization name and unique URL namespace.
        </p>

        <form className="grid gap-4 sm:grid-cols-2" onSubmit={handleUpdateOrg}>
          <Input
            label="Organization name"
            name="name"
            onChange={(e) => setName(e.target.value)}
            required
            value={name}
          />
          <Input
            label="Organization slug"
            name="slug"
            onChange={(e) => setSlug(e.target.value)}
            required
            value={slug}
          />

          <div className="sm:col-span-2">
            <Dropdown
              label="Organization Status"
              name="status"
              onChange={(e) => setStatus(e.target.value)}
              value={status}
            >
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="archived">Archived</option>
            </Dropdown>
          </div>

          {error ? (
            <p className="m-0 text-xs font-semibold text-[var(--danger)] sm:col-span-2" role="alert">
              {error}
            </p>
          ) : null}

          <div className="flex justify-end pt-2 sm:col-span-2">
            <Button
              className="flex items-center gap-2"
              disabled={pending || name.trim().length < 2 || slug.trim().length < 2}
              type="submit"
            >
              <Save aria-hidden size={16} /> {pending ? "Saving…" : "Save organization"}
            </Button>
          </div>
        </form>
      </Card>

      {/* Team & Members */}
      <Card className="overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-[var(--border)] p-6">
          <div>
            <div className="flex items-center gap-2">
              <Users aria-hidden className="text-[var(--accent)]" size={20} />
              <h2 className="m-0 text-lg font-bold">Team Members</h2>
            </div>
            <p className="mb-0 mt-1 text-xs text-[var(--muted)]">
              Manage organization members and assign explicit RBAC roles.
            </p>
          </div>
          <Button
            className="flex items-center gap-2"
            onClick={() => setShowAddMember(true)}
            type="button"
          >
            <UserPlus aria-hidden size={16} /> Add member
          </Button>
        </div>

        <Table>
          <thead>
            <tr>
              <TableHead>User</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Joined</TableHead>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <tr className="transition hover:bg-[var(--surface-soft)]" key={member.id}>
                <TableCell className="font-semibold">
                  <div className="flex items-center gap-2">
                    <span className="grid size-8 place-items-center rounded-full bg-[var(--surface-soft)] text-xs font-bold text-[var(--ink)]">
                      {member.display_name.slice(0, 2).toUpperCase()}
                    </span>
                    <span>{member.display_name}</span>
                  </div>
                </TableCell>
                <TableCell className="font-mono text-xs text-[var(--muted)]">{member.email}</TableCell>
                <TableCell>
                  <select
                    aria-label={`Role for ${member.display_name}`}
                    className="rounded-lg border border-[var(--border)] bg-white px-2.5 py-1 text-xs font-semibold capitalize transition hover:border-[var(--accent)]"
                    onChange={(e) =>
                      handleUpdateMemberRole(
                        member.user_id,
                        e.target.value as OrganizationMember["role"],
                        member.status
                      )
                    }
                    value={member.role}
                  >
                    {ROLES.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </TableCell>
                <TableCell>
                  <span
                    className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-bold capitalize ${
                      member.status === "active"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-red-50 text-red-700"
                    }`}
                  >
                    {member.status}
                  </span>
                </TableCell>
                <TableCell className="text-xs text-[var(--muted)]">
                  {new Date(member.joined_at).toLocaleDateString()}
                </TableCell>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card>

      {/* Role Descriptions Card */}
      <Card className="p-6">
        <div className="flex items-center gap-2">
          <Shield aria-hidden className="text-[var(--accent)]" size={18} />
          <h2 className="m-0 text-base font-bold">Permissions & Role Hierarchy</h2>
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ROLES.map((r) => (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-soft)] p-3" key={r.value}>
              <p className="mb-1 text-xs font-bold text-[var(--ink)]">{r.label}</p>
              <p className="m-0 text-xs text-[var(--muted)]">{r.desc}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Add Member Modal */}
      <Modal onClose={() => setShowAddMember(false)} open={showAddMember} title="Add Organization Member">
        <form className="grid gap-4" onSubmit={handleAddMember}>
          <Input
            label="User UUID"
            name="user_id"
            onChange={(e) => setAddUserId(e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
            required
            value={addUserId}
          />
          <Dropdown
            label="Assign Role"
            name="role"
            onChange={(e) => setAddRole(e.target.value as OrganizationMember["role"])}
            value={addRole}
          >
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label} — {r.desc}
              </option>
            ))}
          </Dropdown>

          {addMemberError ? (
            <p className="m-0 text-xs font-semibold text-[var(--danger)]" role="alert">
              {addMemberError}
            </p>
          ) : null}

          <div className="flex justify-end gap-3 pt-2">
            <Button onClick={() => setShowAddMember(false)} tone="secondary" type="button">
              Cancel
            </Button>
            <Button disabled={addMemberPending || !addUserId.trim()} type="submit">
              {addMemberPending ? "Adding…" : "Add member"}
            </Button>
          </div>
        </form>
      </Modal>

      {toastMessage ? <Toast message={toastMessage} tone="success" /> : null}
    </div>
  );
}
