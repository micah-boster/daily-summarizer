"use client";

import { Scale, CheckSquare, FileText, ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useUIStore } from "@/stores/ui-store";
import type {
  DailySidecar,
  SidecarDecision,
  SidecarCommitment,
  SidecarTask,
} from "@/lib/types";
import type { LucideIcon } from "lucide-react";

interface StructuredCardsProps {
  sidecar: DailySidecar | null;
}

export function StructuredCards({ sidecar }: StructuredCardsProps) {
  if (!sidecar) return null;

  return (
    <div className="flex flex-col gap-4">
      {sidecar.decisions.length > 0 && (
        <SectionCard
          sectionId="card-decisions"
          title="Decisions"
          icon={Scale}
          count={sidecar.decisions.length}
        >
          <div className="flex flex-col gap-3">
            {sidecar.decisions.map((d, i) => (
              <DecisionItem key={i} decision={d} />
            ))}
          </div>
        </SectionCard>
      )}

      {sidecar.commitments.length > 0 && (
        <SectionCard
          sectionId="card-commitments"
          title="Commitments"
          icon={CheckSquare}
          count={sidecar.commitments.length}
        >
          <div className="flex flex-col gap-3">
            {sidecar.commitments.map((c, i) => (
              <CommitmentItem key={i} commitment={c} />
            ))}
          </div>
        </SectionCard>
      )}

      {sidecar.tasks.length > 0 && (
        <SectionCard
          sectionId="card-substance"
          title="Substance"
          icon={FileText}
          count={sidecar.tasks.length}
        >
          <div className="flex flex-col gap-3">
            {sidecar.tasks.map((t, i) => (
              <TaskItem key={i} task={t} />
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Collapsible section card                                           */
/* ------------------------------------------------------------------ */

function SectionCard({
  sectionId,
  title,
  icon: Icon,
  count,
  children,
}: {
  sectionId: string;
  title: string;
  icon: LucideIcon;
  count: number;
  children: React.ReactNode;
}) {
  const collapsed = useUIStore((s) => s.collapsedSections[sectionId] ?? false);
  const toggle = useUIStore((s) => s.toggleSection);

  return (
    <Card>
      <Collapsible open={!collapsed} onOpenChange={() => toggle(sectionId)}>
        <CardHeader className="py-3">
          <CollapsibleTrigger className="flex w-full cursor-pointer items-center gap-2">
            <Icon className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium">{title}</span>
            <Badge variant="secondary" className="ml-1 text-xs">
              {count}
            </Badge>
            <div className="flex-1" />
            {collapsed ? (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            )}
          </CollapsibleTrigger>
        </CardHeader>
        <CollapsibleContent>
          <CardContent className="pt-0">{children}</CardContent>
        </CollapsibleContent>
      </Collapsible>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Individual item renderers                                          */
/* ------------------------------------------------------------------ */

function DecisionItem({ decision }: { decision: SidecarDecision }) {
  return (
    <div className="text-sm">
      <p>{decision.description}</p>
      <div className="mt-1 flex flex-wrap items-center gap-2">
        {decision.decision_makers.length > 0 && (
          <span className="text-xs text-muted-foreground">
            by {decision.decision_makers.join(", ")}
          </span>
        )}
        {decision.rationale && (
          <span className="text-xs italic text-muted-foreground">
            &mdash; {decision.rationale}
          </span>
        )}
        <Badge variant="outline" className="text-xs">
          {decision.source_meeting}
        </Badge>
      </div>
    </div>
  );
}

function CommitmentItem({ commitment }: { commitment: SidecarCommitment }) {
  const deadlineColor = getDeadlineColor(commitment.by_when);

  return (
    <div className="text-sm">
      <p>
        {commitment.what}
        <Badge className="ml-2 text-xs">{commitment.who}</Badge>
        <Badge variant="outline" className={`ml-1 text-xs ${deadlineColor}`}>
          {commitment.by_when}
        </Badge>
      </p>
      {commitment.source.length > 0 && (
        <div className="mt-1">
          {commitment.source.map((s, i) => (
            <Badge key={i} variant="outline" className="mr-1 text-xs">
              {s}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function TaskItem({ task }: { task: SidecarTask }) {
  const statusColor =
    task.status === "completed"
      ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
      : task.status === "in-progress"
        ? "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
        : "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-300";

  return (
    <div className="text-sm">
      <p>
        {task.description}
        {task.owner && (
          <Badge className="ml-2 text-xs">{task.owner}</Badge>
        )}
      </p>
      <div className="mt-1 flex items-center gap-2">
        <Badge variant="outline" className="text-xs">
          {task.source_meeting}
        </Badge>
        <Badge className={`text-xs ${statusColor}`}>{task.status}</Badge>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */

function getDeadlineColor(byWhen: string): string {
  if (byWhen === "unspecified") {
    return "text-yellow-600 border-yellow-300 dark:text-yellow-400 dark:border-yellow-700";
  }
  try {
    const deadline = new Date(byWhen);
    if (isNaN(deadline.getTime())) {
      return "text-yellow-600 border-yellow-300 dark:text-yellow-400 dark:border-yellow-700";
    }
    const now = new Date();
    if (deadline < now) {
      return "text-red-600 border-red-300 dark:text-red-400 dark:border-red-700";
    }
    return "text-green-600 border-green-300 dark:text-green-400 dark:border-green-700";
  } catch {
    return "text-yellow-600 border-yellow-300 dark:text-yellow-400 dark:border-yellow-700";
  }
}
