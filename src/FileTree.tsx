import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import {
  Button,
  Input,
  Menu,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
} from "@fluentui/react-components";
import {
  AddRegular,
  ArrowSyncRegular,
  ChevronDownRegular,
  ChevronRightRegular,
  DeleteRegular,
  DocumentRegular,
  EyeOffRegular,
  EyeRegular,
  FolderRegular,
  MoreHorizontalRegular,
  SearchRegular,
} from "@fluentui/react-icons";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useTranslation } from "react-i18next";
import { api, ApiError, type FileEntry, type Root } from "./api";
import { IconButton } from "./Controls";
import { DirectoryRequests, inside, pathKey, uniqueEntries, selectedEntries as collectSelected, operationEntries, canAct } from "./explorer";
import { explorerShortcut, shortcutLabels } from "./shortcuts";

interface Listing {
  entries: FileEntry[];
  has_more: boolean;
  total: number;
  version: number;
  query: string;
  hidden: boolean;
}
interface Row {
  key: string;
  entry: FileEntry;
  depth: number;
  parent: string;
  root?: boolean;
  more?: boolean;
  notice?: string;
}
export interface FileEvents {
  version: number;
  rescan?: boolean;
  events: { parent?: string; path?: string; rescan?: boolean }[];
}
export function FileTree({
  roots,
  onRoots,
  hidden,
  onHidden,
  onAdd,
  onForget,
  onFiles,
  onFolder,
  onAction,
  onError,
  events,
}: {
  roots: Root[];
  onRoots: (roots: Root[]) => void;
  hidden: boolean;
  onHidden: () => void;
  onAdd: () => void;
  onForget: (path: string) => void;
  onFiles: (files: FileEntry[]) => void;
  onFolder: (path: string) => void;
  onAction: (action: string, entries: FileEntry[], folder: string) => void;
  onError: (e: unknown) => void;
  events: FileEvents;
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(new Set<string>());
  const [listings, setListings] = useState<Record<string, Listing>>({});
  const [selected, setSelected] = useState(new Set<string>());
  const [folder, setFolder] = useState("");
  const [filter, setFilter] = useState("");
  const [query, setQuery] = useState("");
  const [menu, setMenu] = useState("");
  const [busy, setBusy] = useState(new Set<string>());
  const [errors, setErrors] = useState<Record<string, string>>({});
  const scroll = useRef<HTMLDivElement>(null);
  const listingRef = useRef(listings);
  listingRef.current = listings;
  const expandedRef = useRef(expanded);
  const requests = useRef(new DirectoryRequests<Listing>()).current;
  const initialized = useRef(false);
  const scope = useRef({ hidden, query });
  const view = useRef({ roots, hidden, query });
  view.current = { roots, hidden, query };
  useEffect(() => {
    const timer = setTimeout(() => setQuery(filter.trim()), 200);
    return () => clearTimeout(timer);
  }, [filter]);
  useEffect(() => () => requests.cancel(), [requests]);
  const load = useCallback(
    async (path: string, refresh = false, more = false) => {
      if (more && requests.busy(path)) return;
      setBusy((v) => new Set(v).add(path));
      try {
        const previous = listingRef.current[path];
        const sameScope = previous?.query === query && previous.hidden === hidden;
        const data = await requests.run(path, more, async (signal) => {
          const read = (offset: number, limit: number, fresh: boolean) =>
            api<Listing>(`/directory?${new URLSearchParams({
              path, hidden: String(hidden), query, refresh: String(fresh),
              offset: String(offset), limit: String(limit),
            })}`, { signal });
          const append = more && sameScope;
          let result = await read(append ? previous.entries.length : 0, 200, refresh);
          if (append && result.version === previous.version)
            return { ...result, query, hidden, entries: uniqueEntries([...previous.entries, ...result.entries]) };
          // Rebuild the loaded extent if an offset refers to an older snapshot.
          const extent = sameScope && (refresh || more)
            ? Math.max(200, previous.entries.length + (more ? 200 : 0)) : 200;
          if (append) result = await read(0, Math.min(1000, extent), true);
          const entries = [...result.entries];
          while (result.has_more && entries.length < extent) {
            const page = await read(entries.length, Math.min(1000, extent - entries.length), false);
            if (page.version !== result.version) throw new Error("DIRECTORY_CHANGED_RETRY");
            entries.push(...page.entries);
            result = page;
          }
          return { ...result, query, hidden, entries: uniqueEntries(entries) };
        });
        if (data && view.current.hidden === hidden && view.current.query === query && view.current.roots.some((root) => inside(path, root.path))) {
          listingRef.current = { ...listingRef.current, [path]: data };
          setListings((v) => ({ ...v, [path]: data }));
          setErrors((v) => { const next = { ...v }; delete next[path]; return next; });
        }
      } catch (e) {
        setErrors((v) => ({ ...v, [path]: e instanceof ApiError && [403, 404].includes(e.status) ? "unavailable" : "directoryRetry" }));
        if (e instanceof ApiError && [403, 404].includes(e.status))
          setListings((v) => { const next = { ...v }; delete next[path]; return next; });
      } finally {
        if (!requests.busy(path)) setBusy((v) => {
          const n = new Set(v); n.delete(path); return n;
        });
      }
    },
    [hidden, query, requests],
  );
  useEffect(() => {
    const allowed = (path: string) => roots.some((root) => inside(path, root.path));
    requests.cancel(allowed);
    setListings((v) => Object.fromEntries(Object.entries(v).filter(([path]) => allowed(path))));
    setExpanded((v) => new Set([...v].filter(allowed)));
    setErrors((v) => Object.fromEntries(Object.entries(v).filter(([path]) => allowed(path))));
    setMenu("");
    const first = roots.find((r) => r.available);
    if (first && (!initialized.current || (!listingRef.current[first.path] && !requests.busy(first.path)))) {
      initialized.current = true;
      setExpanded((v) => new Set(v).add(first.path));
      void load(first.path);
    }
    setFolder((current) => allowed(current) ? current : first?.path || "");
  }, [roots, requests, load]);
  useEffect(() => {
    if (scope.current.hidden === hidden && scope.current.query === query) return;
    scope.current = { hidden, query };
    requests.cancel();
    for (const path of expandedRef.current) void load(path, true);
  }, [hidden, query, load, requests]);
  useEffect(() => { onFolder(folder); }, [folder, onFolder]);
  useEffect(() => {
    const parents = new Set(events.events.flatMap((e) => e.parent ? [pathKey(e.parent)] : []));
    for (const path of expandedRef.current)
      if (
        events.rescan ||
        events.events.some((e) => e.rescan) ||
        parents.has(pathKey(path)) || events.events.some((e) => e.path && inside(path, e.path))
      )
        void load(path, true);
  }, [events, load]);
  const refresh = async () => {
    try {
      const next = await api<Root[]>("/roots?refresh=true");
      onRoots(next);
      const visibleOrRestored = new Set([...expandedRef.current,
        ...next.filter((root) => root.available && expanded.has(root.path)).map((root) => root.path)]);
      for (const path of visibleOrRestored)
        if (next.some((root) => root.available && inside(path, root.path))) void load(path, true);
    } catch (e) { onError(e); }
  };
  const rows = useMemo(() => {
    const result: Row[] = [];
    const add = (
      entry: FileEntry,
      depth: number,
      parent: string,
      rootPath: string,
      root = false,
    ) => {
      // A physical path can appear under more than one workspace root.
      const key = JSON.stringify([rootPath, entry.path, "item"]);
      result.push({ key, entry, depth, parent, root });
      if (!entry.link && expanded.has(entry.path)) {
        const listing = listings[entry.path];
        const matching = listing?.query === query && listing.hidden === hidden;
        for (const child of listing?.entries || []) {
          if ((hidden || !child.hidden) && (!filter || child.directory || child.name.toLocaleLowerCase().includes(filter.trim().toLocaleLowerCase())))
            add(child, depth + 1, entry.path, rootPath);
        }
        const notice = errors[entry.path] || (!matching ? "loading" : !listing.entries.length ? query ? "noMatches" : "noFiles" : "");
        if (notice) result.push({
          key: JSON.stringify([rootPath, entry.path, "notice"]), entry,
          depth: depth + 1, parent: entry.path, notice,
        });
        if (matching && listing.has_more)
          result.push({
            key: JSON.stringify([rootPath, entry.path, "more"]),
            entry: { ...entry, name: t("loadMore") },
            depth: depth + 1,
            parent: entry.path,
            more: true,
          });
      }
    };
    for (const root of roots)
      add(
        {
          path: root.path,
          name: root.name,
          directory: true,
          size: 0,
          extension: "",
          link: !root.available,
        },
        0,
        root.path,
        root.path,
        true,
      );
    return result;
  }, [roots, listings, expanded, filter, query, hidden, errors, t]);
  expandedRef.current = new Set(rows.filter((row) => !row.more && !row.notice &&
    row.entry.directory && !row.entry.link && expanded.has(row.entry.path)).map((row) => row.entry.path));
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroll.current,
    getItemKey: useCallback((index: number) => rows[index].key, [rows]),
    estimateSize: () => 34,
    overscan: 8,
  });
  const visibleEntries = useMemo(() => uniqueEntries(rows.filter((r) => !r.more && !r.notice).map((r) => r.entry)), [rows]);
  const selectionEntries = useMemo(() => collectSelected(visibleEntries, selected), [visibleEntries, selected]);
  const selectedEntries = () => selectionEntries;
  useEffect(() => {
    const invalid = [...expanded].filter((path) => {
      if (roots.some((root) => pathKey(root.path) === pathKey(path))) return false;
      if (errors[path] === "unavailable") return true;
      const parent = path.slice(0, path.lastIndexOf("\\"));
      const listing = listings[parent];
      return listing && !listing.has_more && listing.hidden === hidden && listing.query === query &&
        !listing.entries.some((entry) => pathKey(entry.path) === pathKey(path));
    });
    if (!invalid.length) return;
    const keep = (path: string) => !invalid.some((folder) => inside(path, folder));
    requests.cancel(keep);
    setExpanded((previous) => new Set([...previous].filter(keep)));
    setListings((previous) => Object.fromEntries(Object.entries(previous).filter(([path]) => keep(path))));
  }, [expanded, roots, listings, errors, hidden, query, requests]);
  useEffect(() => {
    const visible = new Set(visibleEntries.filter((entry) => !entry.link).map((entry) => pathKey(entry.path)));
    setSelected((previous) => {
      const next = new Set([...previous].filter((path) => visible.has(path)));
      return next.size === previous.size ? previous : next;
    });
    if (!rows.some((row) => row.key === menu && !row.more && !row.notice)) setMenu("");
    if (folder && !visibleEntries.some((entry) => entry.directory && !entry.link && pathKey(entry.path) === pathKey(folder)))
      setFolder(roots.find((root) => root.available)?.path || "");
  }, [visibleEntries, rows, menu, folder, roots]);
  const act = (action: string, entries = selectionEntries, destination = folder) => {
    const targets = operationEntries(action, entries);
    if (canAct(action, targets, roots, destination)) onAction(action, targets, destination);
  };
  const focusRow = (index: number) => {
    if (index < 0 || index >= rows.length || rows[index].more || rows[index].notice) return;
    virtual.scrollToIndex(index);
    requestAnimationFrame(() => requestAnimationFrame(() =>
      scroll.current?.querySelector<HTMLElement>(`[data-index="${index}"] [role="treeitem"]`)?.focus(),
    ));
  };
  const toggle = (entry: FileEntry) => {
    if (entry.link) return;
    setExpanded((v) => {
      const n = new Set(v);
      n.has(entry.path) ? n.delete(entry.path) : n.add(entry.path);
      return n;
    });
    if (!expanded.has(entry.path)) void load(entry.path, !!listings[entry.path]);
    setFolder(entry.path);
  };
  const choose = (row: Row, multiple = false) => {
    if (row.entry.link) return;
    const key = pathKey(row.entry.path);
    setSelected((v) =>
      multiple
        ? new Set(
            v.has(key)
              ? [...v].filter((p) => p !== key)
              : [...v, key],
          )
        : new Set([key]),
    );
    const next = row.entry.directory ? row.entry.path : row.parent;
    setFolder(next);
  };
  const handleShortcut = (event: KeyboardEvent<HTMLElement>, entries = selectionEntries, destination = folder) => {
    if (event.defaultPrevented || event.nativeEvent.isComposing || !event.currentTarget.contains(event.target as Node)) return;
    const target = event.target as Element;
    if (target.closest('input, textarea, select, [role="textbox"], [contenteditable]:not([contenteditable="false"])')) return;
    const action = explorerShortcut(event);
    if (!action) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.repeat) return;
    if (action === "selectAll") {
      setSelected(new Set(uniqueEntries(visibleEntries).filter((entry) => canAct("cut", [entry], roots, folder)).map((entry) => pathKey(entry.path))));
    }
    else if (action === "refresh") void refresh();
    else act(action, entries, destination);
  };
  return (
    <section className="file-tree" onKeyDown={handleShortcut}>
      <div className="pane-heading">
        <h2>
          <FolderRegular />
          {t("files")}
        </h2>
        <div className="icon-group">
          <IconButton
            label={t("addFolder")}
            icon={<AddRegular />}
            onClick={onAdd}
          />
          <IconButton
            label={t("refresh")}
            icon={<ArrowSyncRegular />}
            onClick={() => void refresh()}
          />
          <IconButton
            label={t(hidden ? "hideHidden" : "hidden")}
            icon={hidden ? <EyeRegular /> : <EyeOffRegular />}
            onClick={onHidden}
          />
          <IconButton
            label={t("recycle")}
            icon={<DeleteRegular />}
            disabled={!canAct("delete", selectionEntries, roots, folder)}
            onClick={() => act("delete")}
          />
        </div>
      </div>
      <div className="tree-search">
        <Input
          aria-label={t("search")}
          placeholder={t("search")}
          contentBefore={<SearchRegular />}
          value={filter}
          onChange={(_, d) => setFilter(d.value)}
          size="small"
        />
      </div>
      <div
        className="tree-scroll"
        ref={scroll}
        role="tree"
        aria-multiselectable="true"
        aria-label={t("files")}
      >
        {!roots.length && (
          <div className="empty-tree">
            <FolderRegular />
            <p>{t("noRoots")}</p>
            <Button onClick={onAdd}>{t("addFolder")}</Button>
          </div>
        )}
        <div style={{ height: virtual.getTotalSize(), position: "relative" }}>
          {virtual.getVirtualItems().map((item) => {
            const row = rows[item.index],
              entry = row.entry;
            const selection = !entry.link && selected.has(pathKey(entry.path));
            return (
              <div
                key={item.key}
                data-index={item.index}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: item.size,
                  transform: `translateY(${item.start}px)`,
                }}
              >
                {row.notice ? (
                  <div className="tree-notice" title={t(row.notice)} style={{ paddingLeft: 8 + row.depth * 16 }}>
                    {t(row.notice)}
                  </div>
                ) : row.more ? (
                  <Button
                    className="load-more"
                    size="small"
                    appearance="subtle"
                    disabled={busy.has(row.parent)}
                    onClick={() => void load(row.parent, false, true)}
                  >
                    {t("loadMore")}
                  </Button>
                ) : (
                  <div
                    role="treeitem"
                    aria-level={row.depth + 1}
                    aria-expanded={
                      entry.directory ? expanded.has(entry.path) : undefined
                    }
                    aria-selected={selection}
                    aria-disabled={entry.link || undefined}
                    tabIndex={0}
                    className={`tree-row ${selection ? "selected" : ""} ${entry.link ? "unavailable" : ""}`}
                    style={{ paddingLeft: 8 + row.depth * 16 }}
                    title={
                      entry.link
                        ? t(row.root ? "unavailable" : "linkBlocked")
                        : entry.path
                    }
                    onClick={(e) => {
                      if (e.currentTarget.contains(e.target as Node)) choose(row, e.ctrlKey || e.metaKey);
                    }}
                    onDoubleClick={(e) => {
                      if (!e.currentTarget.contains(e.target as Node) || (e.target as HTMLElement).closest("button") || entry.link) return;
                      entry.directory ? toggle(entry) : onFiles([entry]);
                    }}
                    onContextMenu={(e) => {
                      if (!e.currentTarget.contains(e.target as Node)) return;
                      e.preventDefault();
                      e.stopPropagation();
                      if (!selection) choose(row);
                      setMenu(row.key);
                    }}
                    onKeyDown={(e) => {
                      if (e.target !== e.currentTarget) return;
                      handleShortcut(e, selection ? selectionEntries : [entry], entry.directory ? entry.path : row.parent);
                      if (e.defaultPrevented) return;
                      if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
                        e.preventDefault();
                        if (!selection) choose(row);
                        setMenu(row.key);
                        return;
                      }
                      if (e.key === "Delete") {
                        e.preventDefault();
                        act("delete", selection ? selectionEntries : [entry]);
                        return;
                      }
                      if (e.key === "Enter" && !entry.link) {
                        entry.directory ? toggle(entry) : onFiles([entry]);
                        e.preventDefault();
                      }
                      if (
                        e.key === "ArrowRight" &&
                        entry.directory && !entry.link
                      ) {
                        if (!expanded.has(entry.path)) toggle(entry);
                        else if (rows[item.index + 1]?.depth > row.depth) focusRow(item.index + 1);
                        e.preventDefault();
                      }
                      if (e.key === "ArrowLeft") {
                        if (entry.directory && !entry.link && expanded.has(entry.path)) toggle(entry);
                        else {
                          let parent = item.index - 1;
                          while (parent >= 0 && (rows[parent].notice || rows[parent].more || rows[parent].depth >= row.depth)) parent--;
                          focusRow(parent);
                        }
                        e.preventDefault();
                      }
                      if (["ArrowDown", "ArrowUp"].includes(e.key)) {
                        e.preventDefault();
                        const step = e.key === "ArrowDown" ? 1 : -1;
                        let index = item.index + step;
                        while (rows[index]?.more || rows[index]?.notice) index += step;
                        focusRow(index);
                      }
                      if (["Home", "End"].includes(e.key)) {
                        e.preventDefault();
                        const step = e.key === "Home" ? 1 : -1;
                        let index = step === 1 ? 0 : rows.length - 1;
                        while (rows[index]?.more || rows[index]?.notice) index += step;
                        focusRow(index);
                      }
                    }}
                    draggable={!entry.directory && !entry.link}
                    onDragStart={(e) => {
                      const entries = selection
                        ? selectedEntries().filter(
                            (x) => !x.directory && !x.link,
                          )
                        : [entry];
                      e.dataTransfer.setData(
                        "application/x-format-converter-files",
                        JSON.stringify(entries),
                      );
                      e.dataTransfer.effectAllowed = "copy";
                    }}
                  >
                    {entry.directory ? (
                      <button
                        className="tree-disclosure"
                        tabIndex={-1}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggle(entry);
                        }}
                        aria-label={entry.name}
                      >
                        {expanded.has(entry.path) ? (
                          <ChevronDownRegular />
                        ) : (
                          <ChevronRightRegular />
                        )}
                      </button>
                    ) : (
                      <span className="tree-spacer" />
                    )}
                    {entry.directory ? <FolderRegular /> : <DocumentRegular />}
                    <span className="tree-name">{entry.name}</span>
                    {busy.has(entry.path) && <span className="loading-dot" />}
                    <Menu
                      open={menu === row.key}
                      onOpenChange={(_, d) =>
                        setMenu((current) =>
                          d.open ? row.key : current === row.key ? "" : current,
                        )
                      }
                    >
                      <MenuTrigger disableButtonEnhancement>
                        <Button
                          size="small"
                          appearance="subtle"
                          className="row-menu"
                          icon={<MoreHorizontalRegular />}
                          aria-label={t("more")}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </MenuTrigger>
                      <MenuPopover>
                        <MenuList>
                          {!entry.directory && (
                            <MenuItem disabled={entry.link} onClick={() => onFiles([entry])}>
                              {t("addFiles")}
                            </MenuItem>
                          )}
                          {[
                            "rename",
                            "copy",
                            "cut",
                            "paste",
                            "properties",
                            "delete",
                          ].map((action) => (
                            <MenuItem
                              key={action}
                              disabled={!canAct(action, selection ? selectionEntries : [entry], roots, entry.directory ? entry.path : row.parent)}
                              onClick={() =>
                                act(
                                  action,
                                  selection ? selectedEntries() : [entry],
                                  entry.directory ? entry.path : row.parent,
                                )
                              }
                            >
                              {t(action === "delete" ? "recycle" : action)}
                              <span className="shortcut-label">{shortcutLabels[action]}</span>
                            </MenuItem>
                          ))}
                          {entry.directory && (
                            <MenuItem
                              disabled={entry.link}
                              onClick={() =>
                                onAction("output", [entry], entry.path)
                              }
                            >
                              {t("chooseOutput")}
                            </MenuItem>
                          )}
                          {row.root && (
                            <MenuItem onClick={() => onForget(entry.path)}>
                              {t("forgetRoot")}
                            </MenuItem>
                          )}
                        </MenuList>
                      </MenuPopover>
                    </Menu>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="tree-footer" title={folder}>
        {folder || t("rootSelected")}
      </div>
      <div className="tree-actions">
        {["rename", "copy", "cut", "paste", "properties"].map((action) => (
          <Button
            key={action}
            size="small"
            appearance="subtle"
            title={`${t(action)} (${shortcutLabels[action]})`}
            disabled={!canAct(action, selectionEntries, roots, folder)}
            onClick={() => act(action)}
          >
            {t(action)}
          </Button>
        ))}
      </div>
      <details className="tree-shortcuts">
        <summary>{t("keyboardShortcuts")}</summary>
        <p>{t("explorerShortcutsHelp")}</p>
      </details>
    </section>
  );
}
