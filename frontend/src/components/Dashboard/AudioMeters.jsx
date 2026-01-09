import { useEffect, useRef } from 'react';
import { useAgents } from '../../context/AgentContext';

function AudioMeters() {
  const { audioLevels } = useAgents();
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, width, height);

    // Draw meters
    const meterWidth = 30;
    const meterHeight = height - 40;
    const meterSpacing = 50;
    const startY = 30;

    const levels = [
      ...audioLevels.inputs,
      ...audioLevels.outputs
    ];

    const labels = ['IN L', 'IN R', 'OUT L', 'OUT R'];

    levels.forEach((level, index) => {
      const x = 20 + index * meterSpacing;

      // Draw meter background
      ctx.fillStyle = '#1a1a1a';
      ctx.fillRect(x, startY, meterWidth, meterHeight);

      // Draw level
      const levelHeight = meterHeight * level;
      const levelY = startY + meterHeight - levelHeight;

      // Color gradient based on level
      const gradient = ctx.createLinearGradient(x, startY, x, startY + meterHeight);
      if (level > 0.9) {
        gradient.addColorStop(0, '#ef4444'); // Red
        gradient.addColorStop(0.3, '#f59e0b'); // Amber
        gradient.addColorStop(1, '#10b981'); // Green
      } else {
        gradient.addColorStop(0, '#f59e0b'); // Amber
        gradient.addColorStop(1, '#10b981'); // Green
      }

      ctx.fillStyle = gradient;
      ctx.fillRect(x, levelY, meterWidth, levelHeight);

      // Draw peak indicator
      if (audioLevels.peaks[index % 2] > 0) {
        const peakY = startY + meterHeight * (1 - audioLevels.peaks[index % 2]);
        ctx.fillStyle = level > 0.9 ? '#ef4444' : '#3b82f6';
        ctx.fillRect(x, peakY - 2, meterWidth, 4);
      }

      // Draw label
      ctx.fillStyle = '#9ca3af';
      ctx.font = '10px JetBrains Mono, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(labels[index], x + meterWidth / 2, height - 10);

      // Draw dB scale
      if (index === 0) {
        ctx.fillStyle = '#9ca3af';
        ctx.font = '9px JetBrains Mono, monospace';
        ctx.textAlign = 'right';
        ctx.fillText('0', x - 5, startY + 5);
        ctx.fillText('-12', x - 5, startY + meterHeight * 0.4);
        ctx.fillText('-24', x - 5, startY + meterHeight * 0.7);
        ctx.fillText('-∞', x - 5, startY + meterHeight);
      }
    });

    // Draw clipping indicator
    if (audioLevels.clipping) {
      ctx.fillStyle = '#ef4444';
      ctx.fillRect(width - 100, 10, 80, 20);
      ctx.fillStyle = '#ffffff';
      ctx.font = '12px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('CLIPPING!', width - 60, 23);
    }

  }, [audioLevels]);

  return (
    <div className="card">
      <h2 className="card-header">Audio Levels</h2>

      <div className="bg-app-bg rounded-md p-4">
        <canvas
          ref={canvasRef}
          width={250}
          height={200}
          className="w-full"
        />
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-app-text-secondary">
        <span>Peak Hold</span>
        <span className={audioLevels.clipping ? 'text-app-error font-bold' : ''}>
          {audioLevels.clipping ? 'CLIPPING DETECTED' : 'No Clipping'}
        </span>
      </div>
    </div>
  );
}

export default AudioMeters;
