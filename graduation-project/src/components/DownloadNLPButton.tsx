// src/components/DownloadNLPButton.tsx
import React from "react";

interface DownloadNLPButtonProps {
  runId?: string;
}

const DownloadNLPButton = ({ runId }: DownloadNLPButtonProps) => {

  const handleDownload = async () => {
    try {
      // TODO: Replace with real endpoint when backend is ready
      // const response = await fetch(`/api/nlp/results/${runId}`);
      
      // Mock response for testing
      const data = {
        report: "NLP Analysis Report",
        runId: runId || "demo-run",
        timestamp: new Date().toISOString(),
        cause: "Collision",
        confidence: 0.94,
        description: "Two vessels collided near the Ionian Sea strait..."
      };

      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });

      const url = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;
      link.download = `nlp_results_${runId || "demo"}.json`;
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
      Download NLP Results
    </button>
  );
};

export default DownloadNLPButton;