import { Application } from "@splinetool/runtime";
import { useLayoutEffect, useRef, useState, type RefObject } from "react";

interface OrbHeroProps {
  busy: boolean;
  destinationRef: RefObject<HTMLDivElement | null>;
  parked: boolean;
}

interface OrbBounds {
  left: number;
  scale: number;
  top: number;
}

const HERO_ORB_SIZE = 260;
const SIDEBAR_ORB_SIZE = 38;
const RENDER_STAGE_WIDTH = 484;
const RENDER_STAGE_HEIGHT = 414;
const SIDEBAR_ORB_SCALE = SIDEBAR_ORB_SIZE / HERO_ORB_SIZE;
const MAX_MEASURE_ATTEMPTS = 10;
const CAMERA_ZOOM = 1.24 * (360 / RENDER_STAGE_HEIGHT);

export function OrbHero({ busy, destinationRef, parked }: OrbHeroProps) {
  const stageRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [bounds, setBounds] = useState<OrbBounds | null>(null);
  const [loaded, setLoaded] = useState(false);
  const renderedBounds = bounds ?? {
    left: -RENDER_STAGE_WIDTH,
    scale: 1,
    top: -RENDER_STAGE_HEIGHT,
  };

  useLayoutEffect(() => {
    let resizeFrame = 0;
    let measureFrame = 0;
    let observer: ResizeObserver | null = null;
    let cancelled = false;

    const updateBounds = () => {
      const target = destinationRef.current;
      if (!target) return false;
      const rect = target.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const scale = parked ? SIDEBAR_ORB_SCALE : 1;
      setBounds({
        left: rect.left + rect.width / 2 - RENDER_STAGE_WIDTH / 2,
        scale,
        top: rect.top + rect.height / 2 - RENDER_STAGE_HEIGHT / 2,
      });
      return true;
    };

    const setFallbackBounds = () => {
      const fallbackScale = parked ? SIDEBAR_ORB_SCALE : 1;
      const fallbackCenterX = parked ? 56 : window.innerWidth / 2 + 38;
      const fallbackCenterY = parked ? 48 : window.innerHeight / 2;
      setBounds({
        left: fallbackCenterX - RENDER_STAGE_WIDTH / 2,
        scale: fallbackScale,
        top: fallbackCenterY - RENDER_STAGE_HEIGHT / 2,
      });
    };

    const measureWhenReady = (attempt = 0) => {
      if (cancelled) return;
      const measured = updateBounds();
      const target = destinationRef.current;

      if (measured && target && !observer) {
        observer = new ResizeObserver(() => {
          cancelAnimationFrame(resizeFrame);
          resizeFrame = requestAnimationFrame(updateBounds);
        });
        observer.observe(target);
      }

      if (!measured && attempt < MAX_MEASURE_ATTEMPTS) {
        measureFrame = requestAnimationFrame(() => measureWhenReady(attempt + 1));
      }

      if (!measured && attempt >= MAX_MEASURE_ATTEMPTS) {
        setFallbackBounds();
      }
    };

    measureFrame = requestAnimationFrame(() => {
      measureFrame = requestAnimationFrame(() => measureWhenReady());
    });

    const onResize = () => {
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => {
        if (!updateBounds()) setFallbackBounds();
      });
    };

    const fonts = document.fonts;
    fonts?.ready.then(() => {
      if (!cancelled) measureWhenReady();
    });

    window.addEventListener("resize", onResize);
    return () => {
      cancelled = true;
      cancelAnimationFrame(resizeFrame);
      cancelAnimationFrame(measureFrame);
      observer?.disconnect();
      window.removeEventListener("resize", onResize);
    };
  }, [destinationRef, parked]);

  useLayoutEffect(() => {
    if (!canvasRef.current) return;
    const app = new Application(canvasRef.current, { renderMode: "auto" });
    let mounted = true;
    const resizeScene = () => frameScene(app);

    frameScene(app);
    app.load("/orb.splinecode").then(() => {
      app.setBackgroundColor("rgba(0, 0, 0, 0)");
      app.setGlobalEvents(false);
      frameScene(app);
      if (mounted) setLoaded(true);
    }).catch(() => mounted && setLoaded(false));
    window.addEventListener("resize", resizeScene);

    return () => {
      mounted = false;
      window.removeEventListener("resize", resizeScene);
      app.dispose();
    };
  }, []);

  return (
    <div
      ref={stageRef}
      className={`shared-orb ${bounds ? "is-measured" : "is-unmeasured"} ${loaded ? "is-loaded" : "is-loading"} ${parked ? "is-parked" : "is-hero"} ${busy ? "is-thinking" : ""}`}
      style={{
        left: renderedBounds.left,
        top: renderedBounds.top,
        transform: `scale(${renderedBounds.scale})`,
      }}
      role="img"
      aria-label="AI assistant orb"
    >
      <canvas ref={canvasRef} className="spline-orb" />
    </div>
  );
}

function frameScene(app: Application | null) {
  if (!app) return;
  app.setSize(RENDER_STAGE_WIDTH, RENDER_STAGE_HEIGHT);
  app.setZoom(CAMERA_ZOOM);
}
