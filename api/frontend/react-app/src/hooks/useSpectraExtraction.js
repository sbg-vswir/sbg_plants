import { useState } from 'react';
import { extractSpectra } from '../utils/api';
import { useJobPolling } from './useJobPolling';

export function useSpectraExtraction(getPixelRanges, setError, setExtractDisabled) {
  const [jobsBySensor, setJobsBySensor] = useState({});
  const [isPolling, setIsPolling]       = useState(false);
  const [spectraType, setSpectraType]   = useState('radiance'); // 'radiance' | 'reflectance'
  const onAllComplete = () => {
    setIsPolling(false);
    setExtractDisabled(false);
  };
  const { sensorStatuses, resetStatuses } = useJobPolling(jobsBySensor, isPolling, onAllComplete);

  const handleExtractSpectra = async () => {
    setError(null);
    try {
      const pixelRangesBySensor = await getPixelRanges();
      const jobs = await extractSpectra(pixelRangesBySensor, spectraType);
      resetStatuses();
      setJobsBySensor(jobs);
      setIsPolling(true);
      setExtractDisabled(true);
    } catch (err) {
      setError(err.message);
    }
  };

  const reset = () => {
    resetStatuses();
    setJobsBySensor({});
    setIsPolling(false);
  };

  return {
    jobsBySensor,
    sensorStatuses,
    isPolling,
    spectraType,
    setSpectraType,
    handleExtractSpectra,
    reset,
  };
}
