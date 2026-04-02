import { useState } from 'react';
import { useDataQuery } from './useDataQuery';
import { VIEW_CONFIG, VIEW_CONFIGS } from '../viewConfig';

/**
 * Shared state for any page that has a view selector, filters, map and table.
 * QueryPage and IsoFitPage both use this — they only differ in the secondary
 * hook (useSpectraExtraction vs useIsoFitJob) and their layout.
 */
export function useQueryPage() {
  const [view, setView] = useState('plot_pixels_mv');
  const query = useDataQuery(view);

  const viewOptions = Object.entries(VIEW_CONFIG)
    .filter(([, cfg]) => cfg.queryable)
    .map(([key, cfg]) => ({ key, label: cfg.displayName || key }));

  const currentViewConfig = VIEW_CONFIGS[view] || { filters: [] };

  const handleViewChange = (newView) => {
    setView(newView);
    query.reset();
  };

  // onExtra is an optional callback for page-specific reset logic
  const handleReset = (onExtra) => {
    setView('plot_pixels_mv');
    query.reset();
    onExtra?.();
  };

  return {
    view,
    query,
    viewOptions,
    currentViewConfig,
    handleViewChange,
    handleReset,
    hideExtract: !!VIEW_CONFIG[view]?.hideExtract,
  };
}
