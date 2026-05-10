import { useEffect, useState, useRef } from "react";
import {
  Users, Plus, Trash2, Save, X, Mail, Building2, MapPin, Search,
} from "lucide-react";
import { rpc } from "../../api/rpc";
import { str, entity as subEntity, fullName, initials, displayName } from "../../api/entity";
import type { Entity } from "../../api/types";

type Mode = "view" | "edit" | "create";

export function ContactsView() {
  const [contacts, setContacts] = useState<Entity[]>([]);
  const [selected, setSelected] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<Mode>("view");
  const selectedIdRef = useRef<number | null>(null);

  useEffect(() => { selectedIdRef.current = selected?.id ?? null; }, [selected]);
  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    const res = await rpc<Entity[]>("contacts.get_all");
    if (res.ok && res.data) {
      setContacts(res.data);
      const currentId = selectedIdRef.current;
      if (currentId != null) {
        const updated = res.data.find((c) => c.id === currentId);
        setSelected(updated || null);
      }
    }
    setLoading(false);
  }

  function startCreate() {
    setSelected(null);
    setMode("create");
  }

  function selectContact(c: Entity) {
    setSelected(c);
    setMode("view");
  }

  async function handleSave(data: ContactFormData) {
    const contact: Record<string, unknown> = {
      first_name: data.firstName,
      last_name: data.lastName,
      company: data.company,
      email: data.email,
      address: {
        street: data.street,
        number: data.number,
        city: data.city,
        postal_code: data.postalCode,
        country: data.country,
      },
    };
    if (mode === "edit" && selected) {
      contact.id = selected.id;
      const addr = subEntity(selected, "address");
      if (addr) contact.address = { ...contact.address as object, id: addr.id };
    }
    const res = await rpc("contacts.save", { contact });
    if (res.ok) {
      setMode("view");
      await load();
    }
  }

  async function handleDelete(id: number) {
    const res = await rpc("contacts.delete", { id });
    if (res.ok) {
      setSelected(null);
      setMode("view");
      await load();
    }
  }

  const filtered = contacts.filter((c) => {
    if (!search) return true;
    const q = search.toLowerCase();
    const name = displayName(c).toLowerCase();
    const email = str(c, "email").toLowerCase();
    const company = str(c, "company").toLowerCase();
    return name.includes(q) || email.includes(q) || company.includes(q);
  });

  if (loading && contacts.length === 0)
    return <div className="flex items-center justify-center h-full text-secondary">Loading contacts…</div>;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 shrink-0 border-b border-border-subtle">
        <h2 className="text-sm font-semibold">Contacts</h2>
        <ToolbarButton icon={<Plus size={15} />} onClick={startCreate} />
        <div className="relative ml-auto">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input type="text" placeholder="Search…" value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 pr-3 py-1.5 rounded-md text-sm outline-none w-44 bg-bg-card text-primary border border-border-subtle placeholder:text-muted" />
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* List */}
        <div className="w-[320px] shrink-0 flex flex-col overflow-hidden border-r border-border-subtle">
          <div className="flex-1 overflow-y-auto">
            {filtered.length === 0
              ? <div className="p-4 text-sm text-center text-tertiary">{search ? "No matches." : "No contacts."}</div>
              : filtered.map((c) => (
                <ContactRow key={c.id} contact={c}
                  isSelected={selected?.id === c.id && mode !== "create"}
                  onSelect={() => selectContact(c)} />
              ))}
          </div>
          <div className="px-4 py-2 text-xs text-tertiary border-t border-border-subtle">
            {filtered.length} contact{filtered.length !== 1 ? "s" : ""}
          </div>
        </div>

        {/* Detail / Form */}
        <div className="flex-1 overflow-y-auto">
          {mode === "create" ? (
            <ContactForm onSave={handleSave} onCancel={() => { setMode("view"); }} />
          ) : mode === "edit" && selected ? (
            <ContactForm contact={selected} onSave={handleSave}
              onCancel={() => setMode("view")} />
          ) : selected ? (
            <ContactDetail contact={selected}
              onEdit={() => setMode("edit")}
              onDelete={() => handleDelete(selected.id)} />
          ) : (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-tertiary">
              <Users size={36} strokeWidth={1.2} />
              <span className="text-sm">Select a contact</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- List row ---------- */

function ContactRow({ contact, isSelected, onSelect }: {
  contact: Entity; isSelected: boolean; onSelect: () => void;
}) {
  const name = displayName(contact);
  const email = str(contact, "email");
  const company = str(contact, "company");
  const ini = initials(contact);

  return (
    <button onClick={onSelect}
      className={`w-full text-left px-4 py-3 border-b border-border-subtle transition-colors flex items-center gap-3
        ${isSelected ? "bg-bg-selected" : "hover:bg-bg-hover"}`}>
      <div className="w-9 h-9 rounded-full bg-bg-card flex items-center justify-center text-sm font-semibold text-secondary shrink-0">
        {ini}
      </div>
      <div className="min-w-0">
        <div className="text-sm font-medium truncate">{name}</div>
        <div className="flex items-center gap-1.5 text-xs text-tertiary truncate">
          {company && <span>{company}</span>}
          {company && email && <span>·</span>}
          {email && <span>{email}</span>}
        </div>
      </div>
    </button>
  );
}

/* ---------- Detail view ---------- */

function ContactDetail({ contact, onEdit, onDelete }: {
  contact: Entity; onEdit: () => void; onDelete: () => void;
}) {
  const name = displayName(contact);
  const ini = initials(contact);
  const email = str(contact, "email");
  const company = str(contact, "company");
  const addr = subEntity(contact, "address");

  const addrParts = addr ? [
    [str(addr, "street"), str(addr, "number")].filter(Boolean).join(" "),
    [str(addr, "postal_code"), str(addr, "city")].filter(Boolean).join(" "),
    str(addr, "country"),
  ].filter(Boolean) : [];

  return (
    <div className="p-5 space-y-5">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-full bg-bg-card flex items-center justify-center text-xl font-semibold text-secondary">
          {ini}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold">{name}</h1>
          {company && str(contact, "first_name") && (
            <div className="flex items-center gap-1.5 text-sm text-secondary">
              <Building2 size={14} className="text-tertiary" />
              <span>{company}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={onEdit}
            className="px-3 py-1.5 rounded text-sm font-medium bg-bg-card text-secondary hover:text-primary border border-border-subtle transition-colors">
            Edit
          </button>
          <button onClick={onDelete}
            className="p-1.5 rounded text-secondary hover:text-red-400 border border-border-subtle transition-colors"
            title="Delete contact">
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* Info cards */}
      <div className="space-y-3">
        {email && (
          <InfoRow icon={<Mail size={14} />} label="Email" value={email} />
        )}
        {company && (
          <InfoRow icon={<Building2 size={14} />} label="Company" value={company} />
        )}
        {addrParts.length > 0 && (
          <div className="flex items-start gap-3 p-3 rounded-lg bg-bg-card border border-border-subtle">
            <span className="text-tertiary mt-0.5"><MapPin size={14} /></span>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-tertiary mb-1">Address</div>
              {addrParts.map((line, i) => (
                <div key={i} className="text-sm">{line}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-bg-card border border-border-subtle">
      <span className="text-tertiary">{icon}</span>
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-tertiary">{label}</div>
        <div className="text-sm">{value}</div>
      </div>
    </div>
  );
}

/* ---------- Create/Edit form ---------- */

interface ContactFormData {
  firstName: string;
  lastName: string;
  company: string;
  email: string;
  street: string;
  number: string;
  city: string;
  postalCode: string;
  country: string;
}

function formDataFromEntity(contact?: Entity): ContactFormData {
  if (!contact) return { firstName: "", lastName: "", company: "", email: "", street: "", number: "", city: "", postalCode: "", country: "" };
  const addr = subEntity(contact, "address");
  return {
    firstName: str(contact, "first_name"),
    lastName: str(contact, "last_name"),
    company: str(contact, "company"),
    email: str(contact, "email"),
    street: addr ? str(addr, "street") : "",
    number: addr ? str(addr, "number") : "",
    city: addr ? str(addr, "city") : "",
    postalCode: addr ? str(addr, "postal_code") : "",
    country: addr ? str(addr, "country") : "",
  };
}

function ContactForm({ contact, onSave, onCancel }: {
  contact?: Entity; onSave: (data: ContactFormData) => void; onCancel: () => void;
}) {
  const [form, setForm] = useState<ContactFormData>(() => formDataFromEntity(contact));
  const [saving, setSaving] = useState(false);
  const isNew = !contact;

  function update(field: keyof ContactFormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    await onSave(form);
    setSaving(false);
  }

  const hasName = form.firstName.trim() || form.lastName.trim() || form.company.trim();

  return (
    <form onSubmit={handleSubmit} className="p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">{isNew ? "New Contact" : "Edit Contact"}</h2>
        <div className="flex items-center gap-2">
          <button type="button" onClick={onCancel}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-secondary hover:text-primary hover:bg-bg-hover transition-colors">
            <X size={14} /> Cancel
          </button>
          <button type="submit" disabled={saving || !hasName}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium text-accent hover:bg-bg-hover transition-colors disabled:opacity-40">
            <Save size={14} /> {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>

      <Section title="Name">
        <div className="grid grid-cols-2 gap-3">
          <FormField label="First Name" value={form.firstName} onChange={(v) => update("firstName", v)} autoFocus />
          <FormField label="Last Name" value={form.lastName} onChange={(v) => update("lastName", v)} />
        </div>
      </Section>

      <Section title="Details">
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Company" value={form.company} onChange={(v) => update("company", v)} />
          <FormField label="Email" value={form.email} onChange={(v) => update("email", v)} type="email" />
        </div>
      </Section>

      <Section title="Address">
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Street" value={form.street} onChange={(v) => update("street", v)} />
          <FormField label="Number" value={form.number} onChange={(v) => update("number", v)} />
          <FormField label="City" value={form.city} onChange={(v) => update("city", v)} />
          <FormField label="Postal Code" value={form.postalCode} onChange={(v) => update("postalCode", v)} />
          <FormField label="Country" value={form.country} onChange={(v) => update("country", v)} />
        </div>
      </Section>
    </form>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wider text-secondary mb-2">{title}</div>
      {children}
    </div>
  );
}

function FormField({ label, value, onChange, type = "text", autoFocus }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; autoFocus?: boolean;
}) {
  return (
    <div>
      <label className="block text-xs text-tertiary mb-1">{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} autoFocus={autoFocus}
        className="w-full px-3 py-2 rounded-md text-sm bg-bg-card text-primary border border-border-subtle outline-none
          focus:border-accent transition-colors placeholder:text-muted" />
    </div>
  );
}

function ToolbarButton({ icon, label, onClick }: {
  icon: React.ReactNode; label?: string; onClick: () => void;
}) {
  return (
    <button onClick={onClick}
      className="flex items-center gap-1.5 px-2 py-1.5 rounded-md text-sm text-secondary hover:text-primary hover:bg-bg-hover transition-colors">
      {icon}
      {label && <span>{label}</span>}
    </button>
  );
}
