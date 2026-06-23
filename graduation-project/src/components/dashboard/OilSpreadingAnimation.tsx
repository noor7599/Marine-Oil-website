import { useEffect, useRef, useState } from "react";
import L from "leaflet";

/**
 * Oil Spreading Animation Component
 * 
 * Simulates realistic oil spill spreading from a center point
 * using directional wave propagation based on trajectory data.
 */

interface Particle {
  lat: number;
  lon: number;
  mass_oil: number;
}

interface TimeStep {
  time: string;
  particles: Particle[];
}

interface SpreadingProps {
  timeSteps: TimeStep[];
  currentTimeStep: number;
  releaseLocation: { lat: number; lon: number } | null;
  oilMaskDataUrl: string;
  maskDimensions: { width: number; height: number };
  progress: number; // 0 to 1 for animation
}

/**
 * Calculate which pixels should be "revealed" based on distance from center
 * This simulates oil spreading outward from the release point
 */
export function createSpreadingMaskCanvas(
  originalMaskUrl: string,
  maskWidth: number,
  maskHeight: number,
  spreadProgress: number,
  spreadDirection: { dx: number; dy: number } | null
): Promise<string> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";

    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = maskWidth;
      canvas.height = maskHeight;
      const ctx = canvas.getContext("2d")!;

      // Draw original image
      ctx.drawImage(img, 0, 0, maskWidth, maskHeight);

      // Get pixel data
      const imageData = ctx.getImageData(0, 0, maskWidth, maskHeight);
      const data = imageData.data;

      const centerX = maskWidth / 2;
      const centerY = maskHeight / 2;

      // Calculate max distance for normalization
      const maxDist = Math.hypot(centerX, centerY);

      // For each pixel, determine if it should be revealed
      for (let y = 0; y < maskHeight; y++) {
        for (let x = 0; x < maskWidth; x++) {
          const pixelIdx = (y * maskWidth + x) * 4;
          const isOil = data[pixelIdx + 3] > 100; // Has alpha

          if (isOil) {
            // Vector from center to this pixel
            const dx = x - centerX;
            const dy = y - centerY;
            const dist = Math.hypot(dx, dy);
            const normalizedDist = dist / maxDist;

            // If direction is provided, pixels in that direction appear first
            let revealThreshold = spreadProgress;
            if (spreadDirection) {
              // Directional bias: pixels along spread direction appear earlier
              const dirMagnitude = Math.hypot(spreadDirection.dx, spreadDirection.dy);
              if (dirMagnitude > 0.01) {
                const dotProduct =
                  (dx * spreadDirection.dx + dy * spreadDirection.dy) /
                  (dist * dirMagnitude || 1);
                const directionBonus = Math.max(0, dotProduct) * 0.3; // 0 to 0.3 bonus
                revealThreshold = (spreadProgress - directionBonus) * 1.1;
              }
            } else {
              // Without direction, just use radial spread
              revealThreshold = spreadProgress * 1.1;
            }

            // Reveal or hide pixel
            if (normalizedDist > revealThreshold) {
              data[pixelIdx + 3] = 0; // Fully transparent (not yet revealed)
            } else {
              // Smooth edge using proximity to threshold
              const edgeBlend = Math.max(0, Math.min(1, 
                (revealThreshold - normalizedDist) / 0.15
              ));
              data[pixelIdx + 3] = Math.round(edgeBlend * data[pixelIdx + 3]);
            }
          }
        }
      }

      ctx.putImageData(imageData, 0, 0);
      resolve(canvas.toDataURL("image/png"));
    };

    img.onerror = () => {
      console.warn("Failed to load mask image for spreading animation");
      resolve(originalMaskUrl);
    };

    img.src = originalMaskUrl;
  });
}

/**
 * Calculate average spread direction from trajectory
 */
export function calculateSpreadDirection(
  timeSteps: TimeStep[],
  currentIdx: number
): { dx: number; dy: number } | null {
  if (timeSteps.length < 2) return null;

  const startIdx = Math.max(0, currentIdx - 5);
  const endIdx = Math.min(timeSteps.length - 1, currentIdx + 5);

  if (startIdx === endIdx) return null;

  const startStep = timeSteps[startIdx];
  const endStep = timeSteps[endIdx];

  if (!startStep?.particles?.length || !endStep?.particles?.length) return null;

  // Get average positions
  const startAvg = {
    lat: startStep.particles.reduce((s, p) => s + p.lat, 0) / startStep.particles.length,
    lon: startStep.particles.reduce((s, p) => s + p.lon, 0) / startStep.particles.length,
  };

  const endAvg = {
    lat: endStep.particles.reduce((s, p) => s + p.lat, 0) / endStep.particles.length,
    lon: endStep.particles.reduce((s, p) => s + p.lon, 0) / endStep.particles.length,
  };

  return {
    dx: (endAvg.lon - startAvg.lon) * 100, // Scale for pixel coordinates
    dy: (endAvg.lat - startAvg.lat) * 100,
  };
}

/**
 * Render spreading oil animation on canvas overlay
 * This component manages the animation state and canvas updates
 */
export async function updateOilSpreadingOverlay(
  overlay: L.ImageOverlay,
  params: SpreadingProps
): Promise<void> {
  const direction = calculateSpreadDirection(params.timeSteps, params.currentTimeStep);

  const spreadMaskUrl = await createSpreadingMaskCanvas(
    params.oilMaskDataUrl,
    params.maskDimensions.width,
    params.maskDimensions.height,
    params.progress,
    direction
  );

  // Update overlay with new spreading mask
  const overlayElement = overlay.getElement() as HTMLImageElement;
  if (overlayElement) {
    overlayElement.src = spreadMaskUrl;
  }
}

export default {
  createSpreadingMaskCanvas,
  calculateSpreadDirection,
  updateOilSpreadingOverlay,
};
