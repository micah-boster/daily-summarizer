"use client";

import dynamic from "next/dynamic";
import type { Components } from "react-markdown";
import { Skeleton } from "@/components/ui/skeleton";

const ReactMarkdown = dynamic(() => import("react-markdown"), {
  loading: () => (
    <div className="space-y-3">
      <Skeleton className="h-6 w-3/4" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  ),
});

// remark-gfm is imported normally — code-split via the ReactMarkdown dynamic import
import remarkGfm from "remark-gfm";

interface MarkdownRendererProps {
  markdown: string;
}

const components: Components = {
  h2: ({ children, ...props }) => (
    <h2
      className="sticky top-0 z-10 border-b bg-background/95 py-2 text-lg font-semibold backdrop-blur-sm"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="mb-2 mt-4 text-base font-medium" {...props}>
      {children}
    </h3>
  ),
  p: ({ children, ...props }) => (
    <p className="mb-3 text-sm leading-relaxed" {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }) => (
    <ul className="mb-3 list-disc pl-5 text-sm" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="mb-3 list-decimal pl-5 text-sm" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="text-sm leading-relaxed" {...props}>
      {children}
    </li>
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="mb-3 border-l-2 border-muted-foreground/30 bg-muted/30 py-1 pl-4 italic"
      {...props}
    >
      {children}
    </blockquote>
  ),
  code: ({ children, className, ...props }) => {
    // Detect if this is an inline code or code block
    const isBlock = className?.startsWith("language-");
    if (isBlock) {
      return (
        <code
          className={`block overflow-x-auto rounded-md bg-muted p-4 text-xs ${className ?? ""}`}
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code
        className="rounded bg-muted px-1.5 py-0.5 text-xs"
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children, ...props }) => (
    <pre className="mb-3 overflow-x-auto rounded-md bg-muted" {...props}>
      {children}
    </pre>
  ),
  a: ({ children, ...props }) => (
    <a
      className="text-primary underline hover:no-underline"
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    >
      {children}
    </a>
  ),
  table: ({ children, ...props }) => (
    <div className="mb-3 overflow-x-auto">
      <table className="w-full border-collapse text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }) => (
    <th
      className="border border-border bg-muted px-3 py-2 text-left text-xs font-medium"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="border border-border px-3 py-2 text-sm" {...props}>
      {children}
    </td>
  ),
};

export function MarkdownRenderer({ markdown }: MarkdownRendererProps) {
  return (
    <div className="markdown-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
