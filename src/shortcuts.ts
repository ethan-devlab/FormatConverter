interface KeyInput {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
}

export const shortcutLabels: Record<string, string> = {
  copy: "Ctrl+C", cut: "Ctrl+X", paste: "Ctrl+V", rename: "F2",
  delete: "Delete", refresh: "F5", properties: "Alt+Enter", selectAll: "Ctrl+A",
};

export function explorerShortcut(event: KeyInput): string | null {
  const key = event.key.toLowerCase();
  if (event.altKey) return key === "enter" && !event.ctrlKey && !event.metaKey && !event.shiftKey ? "properties" : null;
  if (event.shiftKey) return null;
  if (event.ctrlKey || event.metaKey) return ({c:"copy",x:"cut",v:"paste",a:"selectAll"} as Record<string,string>)[key] || null;
  return ({f2:"rename",f5:"refresh",delete:"delete"} as Record<string,string>)[key] || null;
}
