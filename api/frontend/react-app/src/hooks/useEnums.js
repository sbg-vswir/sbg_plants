// hooks/useEnums.js
import { useEffect, useRef, useState } from 'react';
import { fetchEnums } from '../utils/api';
import { ENUMS } from '../viewConfig';

// Module-level guard — the fetch only ever needs to run once per page load,
// no matter how many times a component using this hook mounts/remounts.
let hasFetched = false;

/**
 * Fetches live enum values from GET /enums once per session and merges them
 * into viewConfig.js's ENUMS object IN PLACE, so every filter dropdown that
 * already reads from ENUMS (directly or via VIEW_CONFIG) picks up new DB
 * enum values without any redeploy.
 *
 * If the request fails, the hardcoded fallback values already in ENUMS are
 * left untouched — the query tool keeps working, just without the latest
 * additions until the next successful load.
 *
 * Call this once, near the top of the authenticated part of the app (see
 * App.jsx) — above everywhere that reads ENUMS/VIEW_CONFIG — so the render
 * this hook triggers once the fetch resolves cascades down to every filter
 * dropdown. Components don't need to consume anything from it, they just
 * keep reading ENUMS as before.
 */
export function useEnums() {
  const mounted = useRef(true);
  const [, forceRerender] = useState(0);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    if (hasFetched) return;
    hasFetched = true;

    fetchEnums()
      .then((liveEnums) => {
        if (!mounted.current) return;
        Object.entries(liveEnums).forEach(([key, values]) => {
          // Only merge keys viewConfig.js already knows about — never let
          // the API silently introduce a filter option list nothing uses.
          if (Array.isArray(ENUMS[key]) && Array.isArray(values)) {
            ENUMS[key].splice(0, ENUMS[key].length, ...values);
          }
        });
        // Trigger a re-render so components that already mounted (and read
        // ENUMS before the fetch resolved) pick up the freshly-mutated arrays.
        forceRerender(n => n + 1);
      })
      .catch((err) => {
        // Keep the hardcoded fallback values in viewConfig.js — don't break
        // the app if the enums Lambda is unavailable.
        console.warn('Failed to load live enum values, using fallback:', err);
        hasFetched = false; // allow a retry on the next mount (e.g. re-login)
      });
  }, []);
}
