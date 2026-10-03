"use client";

import { useEffect } from "react";

const WARNING_TEXT = "⚠️ Security Warning: Copying content or code from the Digital FTE platform is strictly prohibited.";

export function SecurityShield({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const blockShortcut = (event: KeyboardEvent) => {
      const key = event.key?.toLowerCase();
      const ctrlOrMeta = event.ctrlKey || event.metaKey;
      const isDevtoolsCombo =
        key === "f12" ||
        (ctrlOrMeta && event.shiftKey && (key === "i" || key === "j" || key === "c")) ||
        (ctrlOrMeta && key === "u") ||
        (event.altKey && event.metaKey && key === "i");

      if (isDevtoolsCombo) {
        event.preventDefault();
        event.stopPropagation();
        return false;
      }

      return undefined;
    };

    const blockContextMenu = (event: MouseEvent) => {
      event.preventDefault();
      event.stopPropagation();
    };

    const blockCopy = (event: ClipboardEvent) => {
      event.preventDefault();
      event.stopPropagation();
      if (event.clipboardData) {
        event.clipboardData.setData("text/plain", WARNING_TEXT);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      blockShortcut(event);
    };

    document.addEventListener("contextmenu", blockContextMenu, { capture: true });
    document.addEventListener("keydown", onKeyDown, { capture: true });
    document.addEventListener("copy", blockCopy, { capture: true });

    const originalConsoleLog = console.log;
    const originalConsoleWarn = console.warn;
    const originalConsoleError = console.error;

    console.log = () => {};
    console.warn = () => {};
    console.error = () => {};

    const observer = new MutationObserver(() => {
      // Suppress structural tampering attempts while keeping the UI responsive.
    });
    observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });

    return () => {
      document.removeEventListener("contextmenu", blockContextMenu, { capture: true });
      document.removeEventListener("keydown", onKeyDown, { capture: true });
      document.removeEventListener("copy", blockCopy, { capture: true });
      console.log = originalConsoleLog;
      console.warn = originalConsoleWarn;
      console.error = originalConsoleError;
      observer.disconnect();
    };
  }, []);

  return (
    <div className="select-none" style={{ WebkitUserSelect: "none", userSelect: "none" }}>
      {children}
    </div>
  );
}
