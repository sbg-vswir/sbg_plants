import { useEffect, useRef } from 'react';
import { ingestApi } from '../utils/api';

const TERMINAL_STATUSES = new Set(['QAQC_PASS', 'QAQC_FAIL', 'PROMOTED', 'REJECTED']);
const POLL_INTERVAL_MS  = 5000;

/**
 * Polls any batch that is PENDING or QAQC_RUNNING every 5 seconds.
 * Calls onUpdate(batch) whenever a batch status changes.
 * Restarts the interval whenever a batch transitions to an active status (e.g. after recheck).
 */
export function useIngestionPolling(batches, onUpdate) {
  const intervalRef = useRef(null);
  const batchesRef  = useRef(batches);

  // Keep ref in sync so the interval closure always sees the latest batches
  useEffect(() => { batchesRef.current = batches; }, [batches]);

  // Track active batch IDs + statuses so we restart when a batch goes back to active
  const activeKey = batches
    .filter(b => !TERMINAL_STATUSES.has(b.status))
    .map(b => `${b.batch_id}:${b.status}`)
    .join(',');

  useEffect(() => {
    function stopPolling() {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    async function poll() {
      const active = batchesRef.current.filter(b => !TERMINAL_STATUSES.has(b.status));
      if (active.length === 0) {
        stopPolling();
        return;
      }

      await Promise.allSettled(
        active.map(async batch => {
          try {
            const updated = await ingestApi.getBatch(batch.batch_id);
            // Always call onUpdate — not just on status change — so that
            // qaqc_report_presigned_url (regenerated on each GET /ingest/{id})
            // propagates into state after a recheck that fails again with the
            // same QAQC_FAIL status.
            onUpdate(updated);
          } catch {
            // swallow individual poll errors — next tick will retry
          }
        })
      );
    }

    if (!activeKey) return;

    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return stopPolling;
  }, [activeKey]); // eslint-disable-line react-hooks/exhaustive-deps
}
