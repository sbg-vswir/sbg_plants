import { useState, useEffect, useRef } from 'react';
import { pollJobStatus } from '../utils/api';

export function useJobPolling(jobsBySensor, isPolling) {
  const [sensorStatuses, setSensorStatuses] = useState({});
  const intervalsRef = useRef({});

  useEffect(() => {
    Object.values(intervalsRef.current).forEach(clearInterval);
    intervalsRef.current = {};

    if (!isPolling || !jobsBySensor || Object.keys(jobsBySensor).length === 0) return;

    setSensorStatuses(
      Object.fromEntries(
        Object.keys(jobsBySensor).map(key => [key, { status: 'queued', rowsProcessed: 0, downloadUrl: null, error: null }])
      )
    );

    Object.entries(jobsBySensor).forEach(([sensorKey, jobId]) => {
      const poll = async () => {
        try {
          const result = await pollJobStatus(jobId);
          const status = result.status === 'queued' ? 'queued' : (result.presigned_url ? 'complete' : 'running');

          setSensorStatuses(prev => ({
            ...prev,
            [sensorKey]: {
              status,
              rowsProcessed: result.rows_processed || 0,
              downloadUrl: result.presigned_url || null,
              error: null
            }
          }));

          if (result.presigned_url) {
            clearInterval(intervalsRef.current[sensorKey]);
            delete intervalsRef.current[sensorKey];
          }
        } catch (err) {
          setSensorStatuses(prev => ({
            ...prev,
            [sensorKey]: { ...prev[sensorKey], status: 'failed', error: err.message }
          }));
          clearInterval(intervalsRef.current[sensorKey]);
          delete intervalsRef.current[sensorKey];
        }
      };

      poll();
      intervalsRef.current[sensorKey] = setInterval(poll, 2000);
    });

    return () => {
      Object.values(intervalsRef.current).forEach(clearInterval);
      intervalsRef.current = {};
    };
  }, [isPolling, jobsBySensor]);

  return { sensorStatuses };
}