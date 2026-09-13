import {
  Bloom,
  EffectComposer,
  ToneMapping,
  Vignette,
} from "@react-three/postprocessing";
import { ToneMappingMode } from "postprocessing";
import { Lighting } from "./Lighting";
import { Track } from "./Track";
import { CarFleet } from "./CarFleet";
import { CarCues } from "./CarCues";
import { CameraRig } from "./CameraRig";
import { useViewerStore } from "../state/store";
import { computeBounds } from "./world";

/**
 * Scene contents. The Canvas itself owns tone mapping (`flat`) so that the
 * ACES pass at the end of the composer is the single source of truth.
 */
export function Scene() {
  const geometry = useViewerStore((state) => state.geometry);
  const radius = geometry ? computeBounds(geometry).radius : 2000;

  return (
    <>
      <color attach="background" args={["#04060b"]} />
      {/* Fades the far ground into the background so the plane's edge is not a
          hard horizon line. */}
      <fog attach="fog" args={["#04060b", radius * 2.2, radius * 7]} />

      <Lighting />
      <Track />
      <CarFleet />
      <CarCues />
      <CameraRig />

      <EffectComposer>
        <Bloom
          intensity={0.2}
          luminanceThreshold={1.1}
          luminanceSmoothing={0.25}
          mipmapBlur
        />
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
        <Vignette offset={0.22} darkness={0.25} eskil={false} />
      </EffectComposer>
    </>
  );
}
