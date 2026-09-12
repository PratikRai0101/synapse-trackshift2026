import { Environment, Lightformer } from "@react-three/drei";
import { useViewerStore } from "../state/store";
import { computeBounds } from "./world";

/**
 * Key light + local studio environment.
 *
 * The `<Environment>` uses Lightformer children rather than a preset so the
 * cubemap is rendered locally: no HDRI fetch, works offline, and car bodywork
 * still gets believable reflections.
 */
export function Lighting() {
  const geometry = useViewerStore((state) => state.geometry);
  const extent = geometry ? computeBounds(geometry).radius * 1.2 : 1500;

  return (
    <>
      <ambientLight intensity={0.7} />
      <hemisphereLight args={["#9dc0ff", "#24352a", 1.1]} />

      <directionalLight
        castShadow
        position={[extent * 0.6, extent * 1.1, extent * 0.4]}
        intensity={2.8}
        color="#fff4e0"
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0006}
        shadow-camera-near={1}
        shadow-camera-far={extent * 4}
        shadow-camera-left={-extent}
        shadow-camera-right={extent}
        shadow-camera-top={extent}
        shadow-camera-bottom={-extent}
      />

      {/* Fill from the opposite side so bodywork never goes fully black. */}
      <directionalLight
        position={[-extent * 0.8, extent * 0.7, -extent * 0.6]}
        intensity={0.9}
        color="#9dc4ff"
      />

      <Environment resolution={256} frames={1} environmentIntensity={1.1}>
        <color attach="background" args={["#1a2536"]} />
        <Lightformer
          intensity={4.0}
          position={[0, extent, 0]}
          rotation={[-Math.PI / 2, 0, 0]}
          scale={[extent * 2, extent * 2, 1]}
        />
        <Lightformer
          intensity={2.0}
          color="#8fb4ff"
          position={[-extent, extent * 0.5, -extent * 0.7]}
          scale={[extent, extent, 1]}
        />
        <Lightformer
          intensity={1.6}
          color="#ffd7a0"
          position={[extent, extent * 0.4, extent * 0.8]}
          scale={[extent, extent, 1]}
        />
      </Environment>
    </>
  );
}
