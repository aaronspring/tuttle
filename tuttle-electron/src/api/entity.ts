/**
 * Helpers for working with generic Entity dicts from Python.
 * Mirrors Swift's Entity extension methods (str, num, int, bool, etc.)
 */

import type { Entity } from "./types";

export function str(e: Entity, key: string): string {
  const v = e[key];
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return String(v);
}

export function num(e: Entity, key: string): number {
  const v = e[key];
  if (v == null) return 0;
  if (typeof v === "number") return v;
  if (typeof v === "string") return parseFloat(v) || 0;
  return 0;
}

export function int(e: Entity, key: string): number {
  return Math.round(num(e, key));
}

export function bool(e: Entity, key: string): boolean {
  const v = e[key];
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return v !== 0;
  return false;
}

export function entity(e: Entity, key: string): Entity | null {
  const v = e[key];
  if (v && typeof v === "object" && "id" in v) return v as Entity;
  return null;
}

export function list(e: Entity, key: string): Entity[] {
  const v = e[key];
  if (Array.isArray(v)) return v as Entity[];
  return [];
}

export function fullName(e: Entity): string {
  return [str(e, "first_name"), str(e, "last_name")].filter(Boolean).join(" ");
}

export function displayName(e: Entity): string {
  const name = fullName(e);
  if (name) return name;
  const company = str(e, "company");
  if (company) return company;
  const n = str(e, "name");
  if (n) return n;
  return "—";
}

export function initials(e: Entity): string {
  const parts = [str(e, "first_name"), str(e, "last_name")].filter(Boolean);
  if (parts.length === 0) {
    const name = str(e, "name");
    if (name) {
      return name
        .split(" ")
        .slice(0, 2)
        .map((w) => w[0]?.toUpperCase())
        .join("");
    }
    return "?";
  }
  return parts.map((p) => p[0]?.toUpperCase()).join("");
}

export function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export function dateRange(e: Entity): string {
  const start = str(e, "start_date");
  const end = str(e, "end_date");
  if (end) return `${formatDate(start)} – ${formatDate(end)}`;
  if (start) return `From ${formatDate(start)}`;
  return "";
}

export function projectStatus(e: Entity): string {
  const completed = bool(e, "is_completed");
  if (completed) return "Completed";
  const end = str(e, "end_date");
  const start = str(e, "start_date");
  const today = new Date().toISOString().slice(0, 10);
  if (start > today) return "Upcoming";
  if (end && end >= today) return "Active";
  if (!end) return "Active";
  return "Completed";
}

export function invoiceStatus(e: Entity): string {
  if (bool(e, "cancelled")) return "Cancelled";
  if (bool(e, "paid")) return "Paid";
  if (bool(e, "sent")) {
    const contract = entity(e, "contract");
    if (contract) {
      const termDays = num(contract, "term_of_payment");
      const dateStr = str(e, "date");
      if (dateStr && termDays) {
        const due = new Date(dateStr);
        due.setDate(due.getDate() + termDays);
        if (due < new Date()) return "Overdue";
      }
    }
    return "Sent";
  }
  return "Draft";
}
