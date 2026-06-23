// src/components/DownloadAllResourcesButton.tsx
import React from "react";

interface DownloadAllResourcesButtonProps {
  runId?: string;
}

const DownloadAllResourcesButton = ({ runId }: DownloadAllResourcesButtonProps) => {

  const handleDownload = async () => {
    try {
      // TODO: Replace with real endpoint when backend is ready
      // const response = await fetch(`/api/reports/all/${runId}`);
      
      // Mock response for testing
      const data = {
        bundle: "ALL_RESOURCES",
        runId: runId || "demo-run",
        files: [
          "nlp_results.json",
          "decision_report.json",
          "trajectory.kml",
          "visualizations/",
          "simulation_results.nc"
        ],
        timestamp: new Date().toISOString()
      };

      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });

      const url = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;
      link.download = `all_resources_${runId || "demo"}.json`;
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
      className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg disabled:opacity-50"
    >
      Download All Resources
    </button>
  );
};

export default DownloadAllResourcesButton;