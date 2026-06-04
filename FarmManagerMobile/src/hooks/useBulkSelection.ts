import { useCallback, useMemo, useState } from "react";

export function useBulkSelection<T>() {
  const [selectedSet, setSelectedSet] = useState<Set<T>>(() => new Set());

  const selectedIds = useMemo(() => Array.from(selectedSet), [selectedSet]);
  const isSelecting = selectedSet.size > 0;

  const beginSelection = useCallback((id: T) => {
    setSelectedSet(new Set([id]));
  }, []);

  const toggleSelection = useCallback((id: T) => {
    setSelectedSet((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedSet(new Set());
  }, []);

  const isSelected = useCallback((id: T) => selectedSet.has(id), [selectedSet]);

  return {
    isSelecting,
    selectedIds,
    selectedCount: selectedSet.size,
    beginSelection,
    toggleSelection,
    clearSelection,
    isSelected,
  };
}
