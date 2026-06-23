import { useState } from "react";

const HelpSection = () => {
  const [open, setOpen] = useState(false);

  const toggle = () => setOpen((prev) => !prev);
  const helpId = "dashboard-help-card";

  return (
    <div className="mt-8 flex flex-col items-center" aria-live="polite">
      <button
        onClick={toggle}
        aria-expanded={open}
        aria-controls={helpId}
        className="text-sm font-medium px-3 py-1.5 rounded-full border border-border bg-[#0d1b2a] text-[#e0e1dd] hover:bg-opacity-90 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent"
      >
        Need Help? 🆘
      </button>

      {open && (
        <div
          id={helpId}
          className="mt-2 w-full max-w-xl bg-[#0d1b2a] text-[#e0e1dd] p-4 rounded-lg border border-border shadow-lg"
        >
          <h2 className="text-md font-semibold mb-2">How to Use OceanGuard AI</h2>
          <ol className="list-decimal list-inside space-y-1 ml-4">
            <li>
              <strong>Upload SAR Image:</strong> Start by uploading a Sentinel-1 SAR GeoTIFF file to detect
              oil spill candidates.
            </li>
            <li>
              <strong>View Drift Forecast:</strong> See the particle-based dispersion simulation over the next
              24 hours (map tiles require internet).
            </li>
            <li>
              <strong>Review Validation:</strong> The system validates the detection using physics alignment, ML
              classification, and historical risk context.
            </li>
            <li>
              <strong>Generate Report:</strong> Click “Generate Report” to produce an official PDF for coast
              guard dispatch.
            </li>
          </ol>
        </div>
      )}
    </div>
  );
};

export default HelpSection;
