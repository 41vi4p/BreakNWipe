"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

const STORAGE_KEY = "bnw-theme";

// Inline script injected before paint in layout.tsx so the correct theme is
// applied before React hydrates — no flash of the wrong theme. Kept as a
// string so it can run synchronously in <head>.
export const themeInitScript = `(function(){try{var t=localStorage.getItem('${STORAGE_KEY}');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t);}}catch(e){}})();`;

type Theme = "light" | "dark";

function currentTheme(): Theme {
  if (typeof document === "undefined") return "light";
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Read the theme the pre-paint script applied to <html> on mount; the
    // `mounted` gate avoids a hydration mismatch. Canonical theme-toggle pattern.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(currentTheme());
    setMounted(true);
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore storage failures */
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      title={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
    >
      {/* Render both, reveal by mounted theme to avoid a hydration mismatch */}
      {mounted && theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
    </button>
  );
}
