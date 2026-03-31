import { useState } from 'react';
import { extractSpectra } from '../utils/api';
import { useJobPolling } from './useJobPolling';

export function useSpectraExtraction(getPixelRanges, setError, setExtractDisabled) {
  const [jobsBySensor, setJobsBySensor] = useState({});
  const [isPolling, setIsPolling]       = useState(false);
  const { sensorStatuses }              = useJobPolling(jobsBySensor, isPolling);

  const handleExtractSpectra = async () => {
    setError(null);
    try {
      const pixelRangesBySensor = await getPixelRanges();
      const jobs = await extractSpectra(pixelRangesBySensor);
      setJobsBySensor(jobs);
      setIsPolling(true);
      setExtractDisabled(true);
    } catch (err) {
      setError(err.message);
    }
  };

  const reset = () => {
    setJobsBySensor({});
    setIsPolling(false);
  };

  return {
    jobsBySensor,
    sensorStatuses,
    isPolling,
    handleExtractSpectra,
    reset,
  };
}
