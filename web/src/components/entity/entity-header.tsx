"use client";

interface EntityHeaderProps {
  name: string;
  entityType: string;
  aliases: string[];
}

export function EntityHeader({ name, entityType, aliases }: EntityHeaderProps) {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-bold tracking-tight">{name}</h1>
      <span className="inline-block rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {entityType}
      </span>
      {aliases.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {aliases.map((alias) => (
            <span
              key={alias}
              className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
            >
              {alias}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
