import { useState, useEffect, useRef } from 'react';
import { pollJobStatus } from '../utils/api';

/**
 * Custom hook for polling job status
 */
export function useJobPolling(jobId, isPolling) {
  const [rowsProcessed, setRowsProcessed] = useState(0);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [status, setStatus] = useState('queued');
  const [pollingError, setPollingError] = useState(null);
  const pollingInterval = useRef(null);

  useEffect(() => {
    // Clear any existing interval
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
      pollingInterval.current = null;
    }

    if (!isPolling || !jobId) {
      return;
    }

    // Start polling immediately, then every 2 seconds
    const poll = async () => {
      try {
        const result = await pollJobStatus(jobId);
        setStatus(result.status);
        setRowsProcessed(result.rowsProcessed);
        
        if (result.downloadUrl) {
          setDownloadUrl(result.downloadUrl);
          // Stop polling when complete
          if (pollingInterval.current) {
            clearInterval(pollingInterval.current);
            pollingInterval.current = null;
          }
        }
      } catch (err) {
        console.error('Polling error:', err);
        setPollingError(err.message);
        // Stop polling on error
        if (pollingInterval.current) {
          clearInterval(pollingInterval.current);
          pollingInterval.current = null;
        }
      }
    };

    // Poll immediately
    poll();
    
    // Then poll every 2 seconds
    pollingInterval.current = setInterval(poll, 2000);

    // Cleanup on unmount or when dependencies change
    return () => {
      if (pollingInterval.current) {
        clearInterval(pollingInterval.current);
        pollingInterval.current = null;
      }
    };
  }, [isPolling, jobId]);

  return { rowsProcessed, downloadUrl, status, pollingError };
}