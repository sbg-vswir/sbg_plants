import { useEffect, useRef } from 'react';
import { ingestApi } from '../utils/api';

const TERMINAL_STATUSES = new Set(['QAQC_PASS', 'QAQC_FAIL', 'PROMOTED', 'REJECTED']);
const POLL_INTERVAL_MS  = 5000;

/**
 * Polls any batch that is PENDING or QAQC_RUNNING every 5 seconds.
 * Calls onUpdate(batch) whenever a batch status changes.
 * Stops automatically when all batches reach a terminal status.
 */
export function useIngestionPolling(batches, onUpdate) {
  const intervalRef = useRef(null);
  const batchesRef  = useRef(batches);

  // Keep ref in sync so the interval closure always sees the latest batches
  useEffect(() => { batchesRef.current = batches; }, [batches]);

  useEffect(() => {
    function stopPolling() {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    function hasActiveBatches() {
      return batchesRef.current.some(b => !TERMINAL_STATUSES.has(b.status));
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
            if (updated.status !== batch.status) {
              onUpdate(updated);
            }
          } catch {
            // swallow individual poll errors — next tick will retry
          }
        })
      );
    }

    if (!hasActiveBatches()) return;

    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return stopPolling;
  }, [batches.map(b => b.batch_id).join(',')]); // eslint-disable-line react-hooks/exhaustive-deps
}
