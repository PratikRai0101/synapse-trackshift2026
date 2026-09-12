import { Canvas } from "@react-three/fiber";
import { Scene } from "./scene/Scene";
import { Hud } from "./ui/Hud";
import { useTelemetryStream } from "./net/useTelemetryStream";

export default function App() {
  useTelemetryStream();

  return (
    <div className="app">
      <Canvas
        // `flat` hands tone mapping to the ACES pass in the composer.
        flat
        shadows
        dpr={[1, 2]}
        gl={{
          antialias: false,
          powerPreference: "high-performance",
          // The circuit spans kilometres with a sub-metre gap between the track
          // surface and the ground plane; a linear depth buffer cannot resolve
          // that and the ground punches through the track.
          logarithmicDepthBuffer: true,
        }}
        camera={{ fov: 45, near: 5, far: 40000, position: [0, 1200, 1800] }}
        onCreated={({ gl }) => {
          // The ACES pass in the composer reads this global exposure.
          gl.toneMappingExposure = 1.2;
        }}
      >
        <Scene />
      </Canvas>
      <Hud />
    </div>
  );
}
