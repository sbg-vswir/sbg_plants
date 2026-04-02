import React from 'react';
import FilterSection from './FilterSection';

/**
 * Thin wrapper around FilterSection that wires the common props from
 * useQueryPage automatically. Only the page-specific props need to be
 * passed explicitly: onExtractSpectra, extractLabel, onDownloadTable,
 * downloadTableDisabled, onReset.
 */
export default function QueryFilterSection({
  query,
  currentViewConfig,
  view,
  viewOptions,
  onViewChange,
  onReset,
  onExtractSpectra,
  extractLabel,
  onDownloadTable,
  downloadTableDisabled,
  hideExtract,
}) {
  return (
    <FilterSection
      filters={currentViewConfig.filters}
      filterValues={query.filterValues}
      onFilterChange={query.handleFilterChange}
      geojsonFile={query.geojsonFile}
      geojsonKey={query.geojsonResetKey}
      onGeojsonUpload={query.handleGeojsonUpload}
      onApplyFilters={query.handleApplyFilters}
      onNext={query.handleNext}
      pageSize={query.PAGE_SIZE}
      loading={query.loading}
      nextDisabled={query.nextDisabled}
      extractDisabled={query.extractDisabled}
      onExtractSpectra={onExtractSpectra}
      extractLabel={extractLabel}
      onDownloadTable={onDownloadTable}
      downloadTableDisabled={downloadTableDisabled ?? query.downloadTableDisabled}
      view={view}
      views={viewOptions}
      onViewChange={onViewChange}
      onReset={onReset}
      hideExtract={hideExtract}
    />
  );
}
