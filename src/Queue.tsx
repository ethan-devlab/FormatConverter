import { useEffect, useRef, useState } from "react";
import {
  Button,
  Checkbox,
  Menu,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
} from "@fluentui/react-components";
import {
  ArrowDownRegular,
  ArrowUpRegular,
  DismissRegular,
  DocumentRegular,
  InfoRegular,
  ReOrderDotsVerticalRegular,
} from "@fluentui/react-icons";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  sortableKeyboardCoordinates,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useTranslation } from "react-i18next";
import { type QueueItem, size } from "./api";
import { IconButton } from "./Controls";

function QueueRow({
  item,
  selected,
  onSelect,
  onRemove,
  onOptions,
  onMove,
}: {
  item: QueueItem;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onOptions: () => void;
  onMove: (direction: number) => void;
}) {
  const { t } = useTranslation();
  const sortable = useSortable({ id: item.id });
  const [thumb, setThumb] = useState("");
  useEffect(() => {
    let url = "";
    const controller = new AbortController();
    if (/\.(png|jpe?g|webp|heic|heif|bmp|tiff?|avif|ico)$/i.test(item.name))
      fetch("/api/thumbnail", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Format-Converter": "1",
        },
        body: JSON.stringify({ path: item.path }),
        signal: controller.signal,
      })
        .then((r) => (r.ok ? r.blob() : null))
        .then((blob) => {
          if (blob && !controller.signal.aborted) {
            url = URL.createObjectURL(blob);
            setThumb(url);
          }
        })
        .catch(() => {});
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [item.path, item.name]);
  return (
    <div
      ref={sortable.setNodeRef}
      className={`queue-row ${sortable.isDragging ? "dragging" : ""}`}
      style={{
        transform: CSS.Transform.toString(sortable.transform),
        transition: sortable.transition,
      }}
    >
      <Button
        appearance="subtle"
        size="small"
        icon={<ReOrderDotsVerticalRegular />}
        aria-label={t("manual")}
        {...sortable.attributes}
        {...sortable.listeners}
        className="drag-handle"
      />
      <Checkbox checked={selected} aria-label={item.name} onChange={onSelect} />
      <div className="file-thumb">
        {thumb ? <img src={thumb} alt="" /> : <DocumentRegular />}
      </div>
      <div className="queue-file">
        <div title={item.name} className="filename">
          {item.name}
        </div>
        <div className="file-meta">
          {item.extension.slice(1).toUpperCase()} · {size(item.size)}
          {item.pages && ` · ${item.pages}`}
        </div>
      </div>
      <Menu>
        <MenuTrigger disableButtonEnhancement>
          <Button
            icon={<InfoRegular />}
            size="small"
            appearance="subtle"
            aria-label={t("perFile")}
          />
        </MenuTrigger>
        <MenuPopover>
          <MenuList>
            <MenuItem onClick={onOptions}>{t("perFile")}</MenuItem>
            <MenuItem icon={<ArrowUpRegular />} onClick={() => onMove(-1)}>
              {t("up")}
            </MenuItem>
            <MenuItem icon={<ArrowDownRegular />} onClick={() => onMove(1)}>
              {t("down")}
            </MenuItem>
          </MenuList>
        </MenuPopover>
      </Menu>
      <IconButton
        icon={<DismissRegular />}
        label={`${t("remove")}: ${item.name}`}
        onClick={onRemove}
      />
    </div>
  );
}
export function Queue({
  items,
  selected,
  onSelected,
  onItems,
  onOptions,
}: {
  items: QueueItem[];
  selected: Set<string>;
  onSelected: (v: Set<string>) => void;
  onItems: (v: QueueItem[]) => void;
  onOptions: (v: QueueItem) => void;
}) {
  const { t } = useTranslation();
  const scroll = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: items.length,
    getScrollElement: () => scroll.current,
    estimateSize: () => 78,
    overscan: 8,
  });
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );
  const finish = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id)
      onItems(
        arrayMove(
          items,
          items.findIndex((x) => x.id === active.id),
          items.findIndex((x) => x.id === over.id),
        ),
      );
  };
  return (
    <div
      ref={scroll}
      className="queue-scroll"
      role="region"
      aria-label={t("files")}
    >
      {!items.length ? (
        <div className="empty-queue">
          <DocumentRegular />
          <h2>{t("emptyQueue")}</h2>
          <p>{t("emptyHelp")}</p>
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={finish}
          accessibility={{
            screenReaderInstructions: { draggable: t("dragInstructions") },
            announcements: {
              onDragStart: ({ active }) =>
                t("dragStart", {
                  name: items.find((x) => x.id === active.id)?.name,
                }),
              onDragOver: ({ active, over }) =>
                over
                  ? t("dragPosition", {
                      name: items.find((x) => x.id === active.id)?.name,
                      position: items.findIndex((x) => x.id === over.id) + 1,
                    })
                  : undefined,
              onDragEnd: ({ active, over }) =>
                t("dragFinished", {
                  name: items.find((x) => x.id === active.id)?.name,
                  position:
                    items.findIndex((x) => x.id === (over?.id || active.id)) +
                    1,
                }),
              onDragCancel: () => t("dragCancelled"),
            },
          }}
        >
          <SortableContext
            items={items.map((x) => x.id)}
            strategy={verticalListSortingStrategy}
          >
            <div
              style={{ height: virtual.getTotalSize(), position: "relative" }}
            >
              {virtual.getVirtualItems().map((row) => {
                const item = items[row.index];
                return (
                  <div
                    key={item.id}
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: row.size,
                      transform: `translateY(${row.start}px)`,
                    }}
                  >
                    <QueueRow
                      item={item}
                      selected={selected.has(item.id)}
                      onSelect={() => {
                        const next = new Set(selected);
                        next.has(item.id)
                          ? next.delete(item.id)
                          : next.add(item.id);
                        onSelected(next);
                      }}
                      onRemove={() =>
                        onItems(items.filter((x) => x.id !== item.id))
                      }
                      onOptions={() => onOptions(item)}
                      onMove={(direction) => {
                        const next = row.index + direction;
                        if (next >= 0 && next < items.length)
                          onItems(arrayMove(items, row.index, next));
                      }}
                    />
                  </div>
                );
              })}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </div>
  );
}
