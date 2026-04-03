import { useState, useEffect, useRef, useCallback } from 'react';
import { pollJobStatus } from '../utils/api';

/**
 * Fetches job summary once when parentJobId changes.
 * Only polls on an interval when isPolling is explicitly true.
 * Derived status is based on the summary data, not the polling state.
 */
export function useIsoFitPolling(parentJobId, isPolling, pollInterval = 60000) {
  const [jobData, setJobData]       = useState(null);
  const [pollingError, setPollingError] = useState(null);
  const [lastUpdated, setLastUpdated]   = useState(null);
  const intervalRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const fetchOnce = useCallback(async () => {
    if (!parentJobId) return;
    try {
      const result = await pollJobStatus(parentJobId, 'summary');
      setJobData(result);
      setLastUpdated(new Date());
      setPollingError(null);
      return result;
    } catch (err) {
      setPollingError(err.message || 'Error fetching status');
    }
  }, [parentJobId]);

  // Always fetch once when parentJobId changes
  useEffect(() => {
    if (!parentJobId) { setJobData(null); setPollingError(null); return; }
    fetchOnce();
  }, [parentJobId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Interval polling only when isPolling is explicitly true
  useEffect(() => {
    stopPolling();
    if (!isPolling || !parentJobId) return;

    const poll = async () => {
      const result = await fetchOnce();
      if (!result) return;
      const statuses = Object.keys(result.statuses || {});
      const allTerminal = statuses.length > 0 && statuses.every(s => s === 'complete' || s === 'failed');
      if (allTerminal || (result.total_pixels_remaining === 0 && !result.restart_required)) {
        stopPolling();
      }
    };

    intervalRef.current = setInterval(poll, pollInterval);
    return stopPolling;
  }, [isPolling, parentJobId, pollInterval, stopPolling, fetchOnce]);

  // Derive status purely from data
  const deriveStatus = () => {
    if (!jobData) return 'loading';
    if (jobData.total_pixels_remaining === 0 && !jobData.restart_required) return 'complete';
    const statuses = Object.keys(jobData.statuses || {});
    if (statuses.length > 0 && statuses.every(s => s === 'failed')) return 'failed';
    if (statuses.some(s => s === 'failed')) return 'partial';
    if (statuses.some(s => s === 'running' || s === 'inverting')) return 'in_progress';
    if (statuses.some(s => s === 'submitted')) return 'submitted';
    return 'unknown';
  };

  const derivedStatus = deriveStatus();
  const isComplete    = derivedStatus === 'complete';
  const canPoll = derivedStatus === 'in_progress' || derivedStatus === 'submitted';

  return { jobData, pollingError, lastUpdated, isComplete, canPoll, derivedStatus, stopPolling, fetchOnce };
}
