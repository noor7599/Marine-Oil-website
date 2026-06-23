import React, { useEffect, useRef, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface SegmentationOverlayProps {
  originalImage: string;
  maskUrl: string | null;
}

export default function SegmentationOverlay({ originalImage, maskUrl }: SegmentationOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    if (!canvasRef.current || !originalImage) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const img = new Image();
    img.crossOrigin = 'anonymous';
    
    img.onload = () => {
      // Set canvas size to match image
      canvas.width = img.width;
      canvas.height = img.height;

      // Draw original image
      ctx.drawImage(img, 0, 0);

      // Draw mask overlay if available
      if (maskUrl) {
        const maskImg = new Image();
        maskImg.crossOrigin = 'anonymous';
        
        maskImg.onload = () => {
          // Create semi-transparent overlay
          ctx.globalAlpha = 0.5;
          ctx.drawImage(maskImg, 0, 0);
          ctx.globalAlpha = 1.0;
          setIsLoaded(true);
        };
        
        maskImg.src = maskUrl;
      } else {
        setIsLoaded(true);
      }
    };

    img.src = originalImage;
  }, [originalImage, maskUrl]);

  return (
    <div className="relative aspect-square bg-muted rounded-lg overflow-hidden">
      <canvas
        ref={canvasRef}
        className="w-full h-full object-contain"
      />
      
      {/* Loading indicator */}
      {!isLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/50">
          <div className="animate-pulse text-sm">Loading...</div>
        </div>
      )}

      {/* Badge */}
      {isLoaded && maskUrl && (
        <Badge 
          variant="destructive" 
          className="absolute bottom-2 right-2"
        >
          MASK DETECTED
        </Badge>
      )}

      {/* Coordinates */}
      <div className="absolute bottom-2 left-2 bg-background/80 px-2 py-1 rounded text-xs">
        256×256 px
      </div>
    </div>
  );
}