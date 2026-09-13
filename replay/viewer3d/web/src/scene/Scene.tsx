import {
  Bloom,
  EffectComposer,
  ToneMapping,
  Vignette,
  SMAA,
} from "@react-three/postprocessing";
import { ToneMappingMode } from "postprocessing";
import { Sky } from "@react-three/drei";
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
      {/* Neutral daylight presentation, not a reconstruction of event weather. */}
      <color attach="background" args={["#abbfc8"]} />
      <Sky distance={20000} sunPosition={[.6, 1.1, .4]}
        turbidity={3} rayleigh={.7} mieCoefficient={.003} mieDirectionalG={.8} />
      <fog attach="fog" args={["#abbfc8", radius * 2.2, radius * 6]} />

      <Lighting />
      <Track />
      <CarFleet />
      <CarCues />
      <CameraRig />

      <EffectComposer multisampling={0}>
        <Bloom
          intensity={0.2}
          luminanceThreshold={1.1}
          luminanceSmoothing={0.25}
          mipmapBlur
        />
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
        <Vignette offset={0.22} darkness={0.15} eskil={false} />
        <SMAA />
      </EffectComposer>
    </>
  );
}
