import { Calendar } from "lucide-react";
import { format, parseISO } from "date-fns";

interface EmptyStateProps {
  date?: string;
  message?: string;
}

export function EmptyState({ date, message }: EmptyStateProps) {
  const displayMessage =
    message ??
    (date
      ? `No summary for ${format(parseISO(date), "MMMM d, yyyy")}`
      : "No summary available");

  return (
    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
      <Calendar className="mb-4 h-12 w-12 opacity-30" />
      <p className="text-sm">{displayMessage}</p>
    </div>
  );
}
