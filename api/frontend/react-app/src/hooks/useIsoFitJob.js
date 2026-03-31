import { useState } from 'react';
import { submitIsofitRun } from '../utils/api';

export function useIsoFitJob(getPixelRanges, setError, setExtractDisabled) {
  const [isoFitJobId, setIsoFitJobId]         = useState(null);
  const [isIsoFitPolling, setIsIsoFitPolling] = useState(false);

  const handleRunIsoFit = async () => {
    setError(null);
    try {
      const pixelRanges = await getPixelRanges();
      const response    = await submitIsofitRun({ pixel_ranges: pixelRanges });
      const id          = response.data.parent_job_id || response.data.job_id;
      setIsoFitJobId(id);
      setIsIsoFitPolling(true);
      setExtractDisabled(true);
    } catch (err) {
      setError(err.message);
    }
  };

  const reset = () => {
    setIsoFitJobId(null);
    setIsIsoFitPolling(false);
  };

  return {
    isoFitJobId,
    isIsoFitPolling,
    setIsIsoFitPolling,
    setActiveJobId: setIsoFitJobId,
    handleRunIsoFit,
    reset,
  };
}
