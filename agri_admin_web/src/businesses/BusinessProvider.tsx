import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { listBusinesses, switchBusiness } from '../api/businesses';
import type { BusinessRuntimeItem } from '../api/businesses';
import { authStore } from '../stores/authStore';
import { BusinessContext } from './businessContext';
import type { BusinessContextValue } from './businessContext';
import { readStoredBusinessView, storeBusinessView } from './businessContext';
import { businessViews } from './registry';
import type { BusinessView } from './registry';

function initialSelection(views: BusinessView[]): string | null {
  const stored = readStoredBusinessView();
  if (stored && views.some((view) => view.name === stored)) {
    return stored;
  }
  return views[0]?.name ?? null;
}

interface BusinessProviderProps {
  children: ReactNode;
  views?: BusinessView[];
}

export default function BusinessProvider({
  children,
  views = businessViews,
}: BusinessProviderProps) {
  const [selectedName, setSelectedName] = useState<string | null>(() =>
    initialSelection(views),
  );
  const [runtimeItems, setRuntimeItems] = useState<BusinessRuntimeItem[]>([]);
  const [runtimeActive, setRuntimeActive] = useState<string | null>(null);
  const [loading, setLoading] = useState(() => authStore.isLoggedIn());
  const [switchingName, setSwitchingName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    requestRef.current?.abort();
    if (!authStore.isLoggedIn()) {
      setRuntimeItems([]);
      setRuntimeActive(null);
      setError(null);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    requestRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const data = await listBusinesses(controller.signal);
      if (controller.signal.aborted) return;
      setRuntimeItems(data.items);
      setRuntimeActive(data.active);
      setSelectedName((current) => {
        const stored = readStoredBusinessView();
        if (stored && views.some((view) => view.name === stored)) {
          return stored;
        }
        if (data.active && views.some((view) => view.name === data.active)) {
          return data.active;
        }
        return current && views.some((view) => view.name === current)
          ? current
          : views[0]?.name ?? null;
      });
    } catch {
      if (controller.signal.aborted) return;
      setError('业务清单加载失败，请稍后重试');
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, [views]);

  useEffect(() => {
    void load();
    return () => requestRef.current?.abort();
  }, [load]);

  const selectBusiness = useCallback(async (name: string): Promise<boolean> => {
    if (!views.some((view) => view.name === name)) return false;
    if (name === selectedName && name === runtimeActive) return true;

    setSwitchingName(name);
    setError(null);
    try {
      const result = await switchBusiness(name);
      setRuntimeActive(result.active);
      storeBusinessView(name);
      setSelectedName(name);
      await load();
      return true;
    } catch {
      setError('业务切换失败，请稍后重试');
      return false;
    } finally {
      setSwitchingName(null);
    }
  }, [load, runtimeActive, selectedName, views]);

  const refresh = useCallback(() => {
    void load();
  }, [load]);

  const runtimeFor = useCallback(
    (name: string) => runtimeItems.find((item) => item.name === name),
    [runtimeItems],
  );

  const selectedView = useMemo(
    () => views.find((view) => view.name === selectedName) ?? views[0] ?? null,
    [selectedName, views],
  );

  const value = useMemo<BusinessContextValue>(() => ({
    views,
    selectedName,
    selectedView,
    runtimeItems,
    runtimeActive,
    loading,
    switchingName,
    error,
    selectBusiness,
    refresh,
    runtimeFor,
  }), [
    error,
    loading,
    refresh,
    runtimeActive,
    runtimeFor,
    runtimeItems,
    selectBusiness,
    selectedName,
    selectedView,
    switchingName,
    views,
  ]);

  return (
    <BusinessContext.Provider value={value}>
      {children}
    </BusinessContext.Provider>
  );
}
