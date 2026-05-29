import { useEffect, useRef } from "react";
import Chart from "chart.js/auto";

// Wrapper declarativo de Chart.js: recrea el chart cuando cambian type/data/options.
export default function TaxChart({ type, data, options, height = 240 }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    if (chartRef.current) chartRef.current.destroy();
    chartRef.current = new Chart(canvasRef.current, { type, data, options });
    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [type, data, options]);

  return (
    <div className="tx-cwrap" style={{ height }}>
      <canvas ref={canvasRef} />
    </div>
  );
}
