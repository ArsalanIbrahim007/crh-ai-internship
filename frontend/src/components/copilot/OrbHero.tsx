import { Application } from "@splinetool/runtime";
import { useEffect, useRef, useState } from "react";

export function OrbHero() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!canvasRef.current) return;
    const app = new Application(canvasRef.current);
    let mounted = true;

    app
      .load("/orb.splinecode")
      .then(() => mounted && setLoaded(true))
      .catch(() => mounted && setLoaded(false));

    return () => {
      mounted = false;
      app.dispose();
    };
  }, []);

  return (
    <section className="orb-hero" aria-label="AI orb">
      <canvas ref={canvasRef} className="spline-orb" />
      {!loaded && <div className="orb-fallback" aria-hidden="true" />}
      <div className="orb-reflection" aria-hidden="true" />
    </section>
  );
}
