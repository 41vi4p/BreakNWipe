"use client";

import * as React from "react";
import * as RadixDialog from "@radix-ui/react-dialog";
import { Download, ExternalLink, File as FileIcon, X } from "lucide-react";
import { recoveryViewUrl } from "@/lib/api";
import { Button, DataValue, Spinner } from "./ui";

const OVERLAY = "fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in";
const CONTENT =
  "fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-[94vw] max-w-3xl -translate-x-1/2 -translate-y-1/2 flex-col rounded-xl border border-border bg-surface shadow-[var(--shadow)] focus:outline-none";

const TEXT_EXTENSIONS = [".txt", ".md", ".log", ".csv", ".json", ".xml", ".html", ".ini", ".cfg", ".conf", ".yml", ".yaml"];
const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"];
const TEXT_PREVIEW_LIMIT = 256 * 1024;

function extOf(path: string): string {
  const name = path.split("/").pop() ?? path;
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

// Renders a recovered file's contents inline where the browser can (images,
// PDFs, text), and otherwise offers Open/Download -- so browsing a recovery
// result doesn't require leaving the GUI to check what actually came back.
export function RecoveredFileViewer({
  path,
  onOpenChange,
}: {
  path: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const ext = path ? extOf(path) : "";
  const isImage = IMAGE_EXTENSIONS.includes(ext);
  const isPdf = ext === ".pdf";
  const isText = TEXT_EXTENSIONS.includes(ext);
  const name = path ? path.split("/").pop() : "";
  const url = path ? recoveryViewUrl(path) : "";

  const [text, setText] = React.useState<string | null>(null);
  const [truncated, setTruncated] = React.useState(false);
  const [textError, setTextError] = React.useState<string | null>(null);
  const [textLoading, setTextLoading] = React.useState(false);

  React.useEffect(() => {
    if (!path || !isText) {
      // Reset preview state when the target isn't a text file (or the dialog
      // closed) -- intentional prop-driven reset, same pattern as useAsync.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setText(null);
      setTextError(null);
      return;
    }
    let alive = true;
    setTextLoading(true);
    setTextError(null);
    fetch(url)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf = await res.arrayBuffer();
        const clipped = buf.byteLength > TEXT_PREVIEW_LIMIT ? buf.slice(0, TEXT_PREVIEW_LIMIT) : buf;
        if (!alive) return;
        setText(new TextDecoder().decode(clipped));
        setTruncated(buf.byteLength > TEXT_PREVIEW_LIMIT);
      })
      .catch((e: Error) => alive && setTextError(e.message))
      .finally(() => alive && setTextLoading(false));
    return () => {
      alive = false;
    };
  }, [path, isText, url]);

  return (
    <RadixDialog.Root open={!!path} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={OVERLAY} />
        <RadixDialog.Content className={CONTENT}>
          <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3.5">
            <RadixDialog.Title className="min-w-0 truncate text-sm font-semibold text-fg">
              {name}
            </RadixDialog.Title>
            <div className="flex shrink-0 items-center gap-1.5">
              <a href={url} target="_blank" rel="noreferrer">
                <Button variant="ghost" size="sm">
                  <ExternalLink size={14} /> Open
                </Button>
              </a>
              <a href={url} download={name}>
                <Button variant="ghost" size="sm">
                  <Download size={14} /> Download
                </Button>
              </a>
              <RadixDialog.Close className="rounded-md p-1.5 text-fg-subtle transition-colors hover:bg-surface-2 hover:text-fg">
                <X size={16} />
              </RadixDialog.Close>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-auto bg-surface-2/40 p-4">
            {path && isImage && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={url} alt={name} className="mx-auto max-h-full max-w-full rounded-lg object-contain" />
            )}
            {path && isPdf && (
              <iframe src={url} title={name} className="h-[70vh] w-full rounded-lg border border-border bg-white" />
            )}
            {path && isText && (
              <>
                {textLoading && <Spinner label="Loading preview…" />}
                {textError && <div className="text-sm text-danger">{textError}</div>}
                {text !== null && (
                  <>
                    <pre className="data whitespace-pre-wrap break-all text-xs text-fg">{text}</pre>
                    {truncated && (
                      <div className="mt-3 text-xs text-fg-subtle">
                        Preview truncated at 256 KB — use Download for the full file.
                      </div>
                    )}
                  </>
                )}
              </>
            )}
            {path && !isImage && !isPdf && !isText && (
              <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-sm text-fg-muted">
                <FileIcon size={28} className="text-fg-subtle" />
                <div>
                  No inline preview for <DataValue className="text-fg">{ext || "this file type"}</DataValue>.
                  <br />
                  Use Open or Download above.
                </div>
              </div>
            )}
          </div>
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
