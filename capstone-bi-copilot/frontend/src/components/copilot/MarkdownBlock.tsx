import { Check, Copy } from "lucide-react";
import { useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import SyntaxHighlighter from "react-syntax-highlighter/dist/esm/prism-light";
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash";
import css from "react-syntax-highlighter/dist/esm/languages/prism/css";
import javascript from "react-syntax-highlighter/dist/esm/languages/prism/javascript";
import json from "react-syntax-highlighter/dist/esm/languages/prism/json";
import markup from "react-syntax-highlighter/dist/esm/languages/prism/markup";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import sql from "react-syntax-highlighter/dist/esm/languages/prism/sql";
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";

SyntaxHighlighter.registerLanguage("bash", bash);
SyntaxHighlighter.registerLanguage("css", css);
SyntaxHighlighter.registerLanguage("javascript", javascript);
SyntaxHighlighter.registerLanguage("js", javascript);
SyntaxHighlighter.registerLanguage("json", json);
SyntaxHighlighter.registerLanguage("html", markup);
SyntaxHighlighter.registerLanguage("markup", markup);
SyntaxHighlighter.registerLanguage("python", python);
SyntaxHighlighter.registerLanguage("py", python);
SyntaxHighlighter.registerLanguage("sql", sql);
SyntaxHighlighter.registerLanguage("typescript", typescript);
SyntaxHighlighter.registerLanguage("ts", typescript);

interface MarkdownBlockProps {
  content: string;
}

interface CodeBlockProps {
  className?: string;
  children?: React.ReactNode;
}

function CodeBlock({ className, children }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const match = /language-([^\s]+)/.exec(className ?? "");
  const language = match?.[1];
  const content = String(children ?? "").replace(/\n$/, "");

  if (!language && !content.includes("\n")) return <code className="inline-code">{children}</code>;

  async function copyCode() {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="code-block">
      <div className="code-toolbar">
        <span>{language ?? "code"}</span>
        <button type="button" onClick={copyCode} aria-label="Copy code">
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <SyntaxHighlighter
        language={language ?? "text"}
        style={oneLight}
        customStyle={{ margin: 0, padding: "18px", background: "transparent", fontSize: "13px" }}
        codeTagProps={{ style: { fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace' } }}
      >
        {content}
      </SyntaxHighlighter>
    </div>
  );
}

const components: Components = {
  code: CodeBlock,
  a: ({ children, ...props }) => <a {...props} target="_blank" rel="noreferrer">{children}</a>,
  table: ({ children, ...props }) => <div className="table-scroll"><table {...props}>{children}</table></div>,
};

export function MarkdownBlock({ content }: MarkdownBlockProps) {
  return <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{content}</ReactMarkdown></div>;
}
