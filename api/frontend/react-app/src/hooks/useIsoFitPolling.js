import { useState, useEffect, useRef, useCallback } from 'react';
import { pollJobStatus } from '../utils/api';
// import { client } from '../utils/api'; // your existing axios client

/**
 * Polls /isofit_status/{parentJobId} every 5 seconds.
 * Lambda response:
 *   parent_job_id, total_batches, statuses, total_pixels_processed,
 *   total_pixels_remaining, restart_required, restarted_jobs, failed_jobs_pixel_ids
 */
export function useIsoFitPolling(parentJobId, isPolling) {
  const [jobData, setJobData] = useState(null);
  const [pollingError, setPollingError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const intervalRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    stopPolling();
    if (!isPolling || !parentJobId) return;

    const poll = async () => {
        try {
            const result = await pollJobStatus(parentJobId, 'summary');
            setJobData(result);
            setLastUpdated(new Date());
            setPollingError(null);
            if (result.total_pixels_remaining === 0 && !result.restart_required) {
            stopPolling();
            }
        } catch (err) {
            setPollingError(err.response?.status === 404 ? 'Job not found' : err.message || 'Error fetching status');
            stopPolling();
        }
    };

    poll();
    intervalRef.current = setInterval(poll, 10000);
    return stopPolling;
  }, [isPolling, parentJobId, stopPolling]);

  const isComplete = jobData && jobData.total_pixels_remaining === 0 && !jobData.restart_required;
  return { jobData, pollingError, lastUpdated, isComplete, stopPolling };
}