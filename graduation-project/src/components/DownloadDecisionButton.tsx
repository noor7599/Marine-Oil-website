// src/components/DownloadDecisionButton.tsx
import React from "react";

interface DownloadDecisionButtonProps {
  runId?: string;
}

const DownloadDecisionButton = ({ runId }: DownloadDecisionButtonProps) => {

  const handleDownload = async () => {
    try {
      // TODO: Replace with real endpoint when backend is ready
      // const response = await fetch(`/api/reports/decision/${runId}`);
      
      // Mock response for testing
      const data = {
        decision: "CONFIRMED_OIL_SPILL",
        confidence: 0.96,
        physicsValidated: true,
        runId: runId || "demo-run",
        timestamp: new Date().toISOString()
      };

      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });

      const url = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;
      link.download = `decision_report_${runId || "demo"}.json`;
      link.click();

      window.URL.revokeObjectURL(url);

    } catch (error) {
      console.error("Download failed", error);
    }
  };

  return (
    <button 
      onClick={handleDownload}
      disabled={!runId}
      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50"
    >
      Download Decision Report
    </button>
  );
};

export default DownloadDecisionButton;