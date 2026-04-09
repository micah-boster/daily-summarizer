"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useUIStore } from "@/stores/ui-store";
import { usePipelineStore } from "@/stores/pipeline-store";
import {
  useConfig,
  useUpdateConfig,
  type ConfigValidationError,
} from "@/hooks/use-config";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import {
  ChevronDownIcon,
  ChevronUpIcon,
  Loader2Icon,
  AlertTriangleIcon,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Get a nested value from an object by dotted path. */
function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  const parts = path.split(".");
  let current: unknown = obj;
  for (const part of parts) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

/** Set a nested value on an object by dotted path (immutable). */
function setNestedValue(
  obj: Record<string, unknown>,
  path: string,
  value: unknown,
): Record<string, unknown> {
  const parts = path.split(".");
  const result = structuredClone(obj);
  let current: Record<string, unknown> = result;
  for (let i = 0; i < parts.length - 1; i++) {
    if (!(parts[i] in current) || typeof current[parts[i]] !== "object") {
      current[parts[i]] = {};
    }
    current = current[parts[i]] as Record<string, unknown>;
  }
  current[parts[parts.length - 1]] = value;
  return result;
}

/** Convert a list to textarea value (one item per line). */
function listToTextarea(val: unknown): string {
  if (Array.isArray(val)) return val.join("\n");
  return "";
}

/** Convert textarea value to list (split on newlines, filter empty). */
function textareaToList(val: string): string[] {
  return val
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

// ---------------------------------------------------------------------------
// Section config
// ---------------------------------------------------------------------------

interface FieldDef {
  path: string;
  label: string;
  type: "text" | "number" | "bool" | "textarea";
  /** Only show this field when a parent bool field is true */
  showWhen?: string;
}

interface SectionDef {
  id: string;
  title: string;
  fields: FieldDef[];
}

const SECTIONS: SectionDef[] = [
  {
    id: "pipeline",
    title: "Pipeline Settings",
    fields: [
      { path: "pipeline.timezone", label: "Timezone", type: "text" },
      { path: "pipeline.output_dir", label: "Output Directory", type: "text" },
    ],
  },
  {
    id: "sources",
    title: "Sources",
    fields: [
      // Calendars (always shown)
      {
        path: "calendars.ids",
        label: "Calendar IDs",
        type: "textarea",
      },
      {
        path: "calendars.exclude_patterns",
        label: "Calendar Exclude Patterns",
        type: "textarea",
      },
      // Slack
      { path: "slack.enabled", label: "Slack Enabled", type: "bool" },
      {
        path: "slack.channels",
        label: "Slack Channels",
        type: "textarea",
        showWhen: "slack.enabled",
      },
      {
        path: "slack.dms",
        label: "Slack DMs",
        type: "textarea",
        showWhen: "slack.enabled",
      },
      {
        path: "slack.thread_min_replies",
        label: "Min Thread Replies",
        type: "number",
        showWhen: "slack.enabled",
      },
      {
        path: "slack.thread_min_participants",
        label: "Min Thread Participants",
        type: "number",
        showWhen: "slack.enabled",
      },
      {
        path: "slack.max_messages_per_channel",
        label: "Max Messages per Channel",
        type: "number",
        showWhen: "slack.enabled",
      },
      {
        path: "slack.bot_allowlist",
        label: "Bot Allowlist",
        type: "textarea",
        showWhen: "slack.enabled",
      },
      {
        path: "slack.discovery_check_days",
        label: "Discovery Check Days",
        type: "number",
        showWhen: "slack.enabled",
      },
      {
        path: "slack.user_cache_ttl_days",
        label: "User Cache TTL (days)",
        type: "number",
        showWhen: "slack.enabled",
      },
      // Google Docs
      {
        path: "google_docs.enabled",
        label: "Google Docs Enabled",
        type: "bool",
      },
      {
        path: "google_docs.content_max_chars",
        label: "Content Max Chars",
        type: "number",
        showWhen: "google_docs.enabled",
      },
      {
        path: "google_docs.comment_max_chars",
        label: "Comment Max Chars",
        type: "number",
        showWhen: "google_docs.enabled",
      },
      {
        path: "google_docs.max_docs_per_day",
        label: "Max Docs per Day",
        type: "number",
        showWhen: "google_docs.enabled",
      },
      {
        path: "google_docs.exclude_ids",
        label: "Exclude Doc IDs",
        type: "textarea",
        showWhen: "google_docs.enabled",
      },
      {
        path: "google_docs.exclude_title_patterns",
        label: "Exclude Title Patterns",
        type: "textarea",
        showWhen: "google_docs.enabled",
      },
      // HubSpot
      { path: "hubspot.enabled", label: "HubSpot Enabled", type: "bool" },
      {
        path: "hubspot.access_token",
        label: "Access Token",
        type: "text",
        showWhen: "hubspot.enabled",
      },
      {
        path: "hubspot.ownership_scope",
        label: "Ownership Scope",
        type: "text",
        showWhen: "hubspot.enabled",
      },
      {
        path: "hubspot.owner_id",
        label: "Owner ID",
        type: "text",
        showWhen: "hubspot.enabled",
      },
      {
        path: "hubspot.max_deals",
        label: "Max Deals",
        type: "number",
        showWhen: "hubspot.enabled",
      },
      {
        path: "hubspot.max_contacts",
        label: "Max Contacts",
        type: "number",
        showWhen: "hubspot.enabled",
      },
      {
        path: "hubspot.max_tickets",
        label: "Max Tickets",
        type: "number",
        showWhen: "hubspot.enabled",
      },
      {
        path: "hubspot.max_activities_per_type",
        label: "Max Activities per Type",
        type: "number",
        showWhen: "hubspot.enabled",
      },
      {
        path: "hubspot.portal_url",
        label: "Portal URL",
        type: "text",
        showWhen: "hubspot.enabled",
      },
      // Notion
      { path: "notion.enabled", label: "Notion Enabled", type: "bool" },
      {
        path: "notion.token",
        label: "API Token",
        type: "text",
        showWhen: "notion.enabled",
      },
      {
        path: "notion.content_max_chars",
        label: "Content Max Chars",
        type: "number",
        showWhen: "notion.enabled",
      },
      {
        path: "notion.max_pages_per_day",
        label: "Max Pages per Day",
        type: "number",
        showWhen: "notion.enabled",
      },
      {
        path: "notion.max_db_items_per_day",
        label: "Max DB Items per Day",
        type: "number",
        showWhen: "notion.enabled",
      },
      {
        path: "notion.watched_databases",
        label: "Watched Database IDs",
        type: "textarea",
        showWhen: "notion.enabled",
      },
      {
        path: "notion.notion_version",
        label: "Notion API Version",
        type: "text",
        showWhen: "notion.enabled",
      },
    ],
  },
  {
    id: "transcripts",
    title: "Transcripts",
    fields: [
      {
        path: "transcripts.gemini_drive.enabled",
        label: "Gemini Drive Enabled",
        type: "bool",
      },
      {
        path: "transcripts.gemini.sender_patterns",
        label: "Gemini Sender Patterns",
        type: "textarea",
      },
      {
        path: "transcripts.gemini.subject_patterns",
        label: "Gemini Subject Patterns",
        type: "textarea",
      },
      {
        path: "transcripts.gong.sender_patterns",
        label: "Gong Sender Patterns",
        type: "textarea",
      },
      {
        path: "transcripts.gong.subject_patterns",
        label: "Gong Subject Patterns",
        type: "textarea",
      },
      {
        path: "transcripts.matching.time_window_minutes",
        label: "Matching Time Window (min)",
        type: "number",
      },
      {
        path: "transcripts.matching.include_unmatched_events",
        label: "Include Unmatched Events",
        type: "bool",
      },
      {
        path: "transcripts.preprocessing.strip_filler",
        label: "Strip Filler Words",
        type: "bool",
      },
    ],
  },
  {
    id: "synthesis",
    title: "Synthesis",
    fields: [
      { path: "synthesis.model", label: "Model", type: "text" },
      {
        path: "synthesis.extraction_max_output_tokens",
        label: "Extraction Max Tokens",
        type: "number",
      },
      {
        path: "synthesis.synthesis_max_output_tokens",
        label: "Synthesis Max Tokens",
        type: "number",
      },
      {
        path: "synthesis.weekly_max_output_tokens",
        label: "Weekly Max Tokens",
        type: "number",
      },
      {
        path: "synthesis.monthly_max_output_tokens",
        label: "Monthly Max Tokens",
        type: "number",
      },
      {
        path: "synthesis.max_concurrent_extractions",
        label: "Max Concurrent Extractions",
        type: "number",
      },
    ],
  },
  {
    id: "processing",
    title: "Processing",
    fields: [
      { path: "dedup.enabled", label: "Dedup Enabled", type: "bool" },
      {
        path: "dedup.similarity_threshold",
        label: "Similarity Threshold",
        type: "number",
        showWhen: "dedup.enabled",
      },
      {
        path: "dedup.log_dir",
        label: "Dedup Log Directory",
        type: "text",
        showWhen: "dedup.enabled",
      },
      { path: "entity.enabled", label: "Entity Enabled", type: "bool" },
      {
        path: "entity.db_path",
        label: "Entity DB Path",
        type: "text",
        showWhen: "entity.enabled",
      },
      {
        path: "entity.auto_create",
        label: "Auto-create Entities",
        type: "bool",
        showWhen: "entity.enabled",
      },
      {
        path: "entity.auto_register_threshold",
        label: "Auto-register Threshold",
        type: "number",
        showWhen: "entity.enabled",
      },
      {
        path: "entity.review_threshold",
        label: "Review Threshold",
        type: "number",
        showWhen: "entity.enabled",
      },
      {
        path: "cache.raw_ttl_days",
        label: "Raw Cache TTL (days)",
        type: "number",
      },
      {
        path: "cache.dedup_log_ttl_days",
        label: "Dedup Log TTL (days)",
        type: "number",
      },
    ],
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ConfigPanel() {
  const open = useUIStore((s) => s.configPanelOpen);
  const setOpen = useUIStore((s) => s.setConfigPanelOpen);
  const toggleSection = useUIStore((s) => s.toggleSection);
  const collapsedSections = useUIStore((s) => s.collapsedSections);

  const pipelineStatus = usePipelineStore((s) => s.status);
  const isLocked = pipelineStatus === "running";

  const { data: serverConfig, isLoading } = useConfig();

  // Local form state -- deep clone of server config
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Reset form data when server config loads or panel opens
  useEffect(() => {
    if (serverConfig && open) {
      setFormData(structuredClone(serverConfig));
      setFieldErrors({});
    }
  }, [serverConfig, open]);

  const handleFieldErrors = useCallback(
    (errors: ConfigValidationError[]) => {
      const errMap: Record<string, string> = {};
      for (const e of errors) {
        errMap[e.field] = e.message;
      }
      setFieldErrors(errMap);
    },
    [],
  );

  const mutation = useUpdateConfig({ onFieldErrors: handleFieldErrors });

  // Check if form is dirty (different from server config)
  const isDirty = useMemo(() => {
    if (!serverConfig) return false;
    return JSON.stringify(formData) !== JSON.stringify(serverConfig);
  }, [formData, serverConfig]);

  function updateField(path: string, value: unknown) {
    setFormData((prev) => setNestedValue(prev, path, value));
    // Clear field error on change
    if (fieldErrors[path]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[path];
        return next;
      });
    }
  }

  function handleSave() {
    setFieldErrors({});
    mutation.mutate(formData);
  }

  function shouldShowField(field: FieldDef): boolean {
    if (!field.showWhen) return true;
    return Boolean(getNestedValue(formData, field.showWhen));
  }

  function renderField(field: FieldDef) {
    if (!shouldShowField(field)) return null;

    const value = getNestedValue(formData, field.path);
    const error = fieldErrors[field.path];

    switch (field.type) {
      case "bool":
        return (
          <div key={field.path} className="flex items-center justify-between py-1.5">
            <Label htmlFor={field.path} className="text-sm">
              {field.label}
            </Label>
            <Switch
              id={field.path}
              checked={Boolean(value)}
              onCheckedChange={(checked) => updateField(field.path, checked)}
            />
          </div>
        );

      case "number":
        return (
          <div key={field.path} className="space-y-1.5">
            <Label htmlFor={field.path} className="text-sm">
              {field.label}
            </Label>
            <Input
              id={field.path}
              type="number"
              step="any"
              value={value != null ? String(value) : ""}
              onChange={(e) => {
                const v = e.target.value;
                updateField(
                  field.path,
                  v === "" ? null : Number(v),
                );
              }}
              aria-invalid={!!error}
              className={error ? "border-destructive" : ""}
            />
            {error && (
              <p className="text-xs text-destructive">{error}</p>
            )}
          </div>
        );

      case "textarea":
        return (
          <div key={field.path} className="space-y-1.5">
            <Label htmlFor={field.path} className="text-sm">
              {field.label}
            </Label>
            <Textarea
              id={field.path}
              rows={3}
              value={listToTextarea(value)}
              onChange={(e) =>
                updateField(field.path, textareaToList(e.target.value))
              }
              placeholder="One item per line"
              aria-invalid={!!error}
              className={error ? "border-destructive" : ""}
            />
            {error && (
              <p className="text-xs text-destructive">{error}</p>
            )}
          </div>
        );

      case "text":
      default:
        return (
          <div key={field.path} className="space-y-1.5">
            <Label htmlFor={field.path} className="text-sm">
              {field.label}
            </Label>
            <Input
              id={field.path}
              type="text"
              value={typeof value === "string" ? value : (value != null ? String(value) : "")}
              onChange={(e) => updateField(field.path, e.target.value)}
              aria-invalid={!!error}
              className={error ? "border-destructive" : ""}
            />
            {error && (
              <p className="text-xs text-destructive">{error}</p>
            )}
          </div>
        );
    }
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent side="right" className="w-[540px] sm:max-w-[540px] flex flex-col">
        <SheetHeader>
          <SheetTitle>Pipeline Configuration</SheetTitle>
          <SheetDescription>
            Edit pipeline settings. Changes are saved atomically with a backup.
          </SheetDescription>
        </SheetHeader>

        {isLocked && (
          <div className="mx-4 flex items-center gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
            <AlertTriangleIcon className="size-4 shrink-0" />
            Config locked while pipeline is running
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2Icon className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <fieldset disabled={isLocked} className="space-y-3">
              {SECTIONS.map((section) => {
                const isCollapsed = collapsedSections[`config-${section.id}`];
                return (
                  <Collapsible
                    key={section.id}
                    open={!isCollapsed}
                    onOpenChange={() => toggleSection(`config-${section.id}`)}
                  >
                    <div className="rounded-lg border">
                      <CollapsibleTrigger className="flex w-full items-center justify-between px-3 py-2 text-sm font-medium hover:bg-muted/50">
                        {section.title}
                        {isCollapsed ? (
                          <ChevronDownIcon className="size-4" />
                        ) : (
                          <ChevronUpIcon className="size-4" />
                        )}
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <div className="space-y-3 px-3 pb-3">
                          {section.fields.map((field) =>
                            renderField(field),
                          )}
                        </div>
                      </CollapsibleContent>
                    </div>
                  </Collapsible>
                );
              })}
            </fieldset>
          )}
        </div>

        <SheetFooter>
          <Button
            onClick={handleSave}
            disabled={!isDirty || isLocked || mutation.isPending}
            className="w-full"
          >
            {mutation.isPending && (
              <Loader2Icon className="mr-1.5 size-4 animate-spin" />
            )}
            Save Configuration
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
