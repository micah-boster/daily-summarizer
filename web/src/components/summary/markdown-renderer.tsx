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
  h1: ({ children, ...props }) => (
    <h1
      className="mt-8 mb-4 text-xl font-semibold tracking-tight"
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2
      className="sticky top-0 z-10 mt-8 mb-3 border-b border-border bg-background/95 pb-2 text-lg font-semibold tracking-tight backdrop-blur-sm"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3 className="mt-6 mb-2 text-base font-medium" {...props}>
      {children}
    </h3>
  ),
  h4: ({ children, ...props }) => (
    <h4 className="mt-4 mb-1.5 text-sm font-medium" {...props}>
      {children}
    </h4>
  ),
  p: ({ children, ...props }) => (
    <p className="mb-4 text-sm leading-relaxed" {...props}>
      {children}
    </p>
  ),
  strong: ({ children, ...props }) => (
    <strong className="font-semibold" {...props}>
      {children}
    </strong>
  ),
  ul: ({ children, ...props }) => (
    <ul className="mb-4 list-disc space-y-1.5 pl-5 text-sm" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol className="mb-4 list-decimal space-y-1.5 pl-5 text-sm" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="pl-1 text-sm leading-relaxed" {...props}>
      {children}
    </li>
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="mb-4 border-l-2 border-primary/40 bg-primary/5 py-2 pl-4 text-sm italic text-muted-foreground"
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
          className={`block text-[13px] font-mono leading-relaxed ${className ?? ""}`}
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code
        className="rounded-md bg-muted px-1.5 py-0.5 text-[13px] font-mono"
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children, ...props }) => (
    <pre
      className="mb-4 overflow-x-auto rounded-lg border border-border bg-muted/50 p-4"
      {...props}
    >
      {children}
    </pre>
  ),
  a: ({ children, ...props }) => (
    <a
      className="text-primary underline decoration-primary/30 transition-colors hover:decoration-primary"
      target="_blank"
      rel="noopener noreferrer"
      {...props}
    >
      {children}
    </a>
  ),
  hr: ({ ...props }) => (
    <hr className="my-8 border-t border-border" {...props} />
  ),
  table: ({ children, ...props }) => (
    <div className="mb-4 overflow-x-auto rounded-lg border border-border">
      <table className="w-full border-collapse text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }) => (
    <th
      className="bg-muted/50 px-4 py-2.5 text-left text-xs font-medium uppercase tracking-wider"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="border-t border-border px-4 py-2.5 text-sm" {...props}>
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
