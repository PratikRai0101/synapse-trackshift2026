import { useMemo } from "react";
import * as THREE from "three";
import { useViewerStore } from "../state/store";
import { buildStripGeometry, computeBounds, sceneX, sceneZ } from "./world";
import { insetEdge } from "./trackDetails";
import { drsZoneRanges } from "./cues";

/**
 * The circuit surface: asphalt ribbon, alternating kerbs, ground plane and a
 * start/finish line.
 *
 * Everything is derived from `track_geometry` in the payload (centreline plus
 * inner/outer edges), which the bridge guarantees to deliver exactly once.
 */

interface StripData {
  positions: Float32Array;
  indices: Uint32Array;
  colors?: Float32Array;
}

function toGeometry(data: StripData): THREE.BufferGeometry {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(data.positions, 3));
  geometry.setIndex(new THREE.BufferAttribute(data.indices, 1));
  if (data.colors) {
    geometry.setAttribute("color", new THREE.BufferAttribute(data.colors, 3));
  }
  geometry.computeVertexNormals();
  return geometry;
}

const KERB_PALETTE: [number, number, number][] = [
  [0.92, 0.14, 0.16],
  [1.0, 1.0, 1.0],
];

export function Track() {
  const geometry = useViewerStore((state) => state.geometry);
  const origin = useViewerStore((state) => state.origin);

  const built = useMemo(() => {
    if (!geometry || !origin) return null;

    const {
      x,
      y,
      x_inner: innerX,
      y_inner: innerY,
      x_outer: outerX,
      y_outer: outerY,
    } = geometry;

    // Fall back to the centreline if a payload ever lacks edge arrays.
    const hasEdges =
      innerX?.length && innerY?.length && outerX?.length && outerY?.length;

    const iX = hasEdges ? innerX : x;
    const iY = hasEdges ? innerY : y;
    const oX = hasEdges ? outerX : x;
    const oY = hasEdges ? outerY : y;

    const asphalt = toGeometry(
      buildStripGeometry(iX, iY, oX, oY, origin, 0.0),
    );

    // Match the car's world-space scale, not a percentage of the stylized
    // ribbon. This avoids gigantic kerbs on wide source geometry.
    const { x: innerKerbNearX, y: innerKerbNearY } = insetEdge(iX, iY, x, y, .9);
    const { x: outerKerbNearX, y: outerKerbNearY } = insetEdge(oX, oY, x, y, .9);
    const innerPaint = insetEdge(innerKerbNearX, innerKerbNearY, x, y, .15);
    const outerPaint = insetEdge(outerKerbNearX, outerKerbNearY, x, y, .15);
    const innerLine = toGeometry(buildStripGeometry(innerKerbNearX, innerKerbNearY, innerPaint.x, innerPaint.y, origin, .025));
    const outerLine = toGeometry(buildStripGeometry(outerKerbNearX, outerKerbNearY, outerPaint.x, outerPaint.y, origin, .025));

    const kerbColor = (station: number): [number, number, number] =>
      KERB_PALETTE[Math.floor(station / 8) % 2];

    const innerKerb = toGeometry(
      buildStripGeometry(iX, iY, innerKerbNearX, innerKerbNearY, origin, 0.02, kerbColor),
    );
    const outerKerb = toGeometry(
      buildStripGeometry(oX, oY, outerKerbNearX, outerKerbNearY, origin, 0.02, kerbColor),
    );

    // Start/finish line at station 0, laid across the track.
    const second = Math.min(4, x.length - 1);
    const dx = x[second] - x[0];
    const dy = y[second] - y[0];
    const heading = Math.atan2(dx, dy);
    const trackWidth = hasEdges
      ? Math.hypot(oX[0] - iX[0], oY[0] - iY[0])
      : 200;

    const line = new THREE.BoxGeometry(trackWidth, 0.025, .4);

    const bounds = computeBounds(geometry);

    // DRS splits, reusing the index ranges the 2D replay already computes. Drawn
    // as a thin strip just inside the outer edge so they read as a track marking.
    const drsZones = drsZoneRanges(geometry).map((zone) => {
      const start = zone.start;
      const end = Math.min(zone.end, outerX.length - 1);
      const slice = (values: number[]) => values.slice(start, end + 1);
      const outerSliceX = slice(oX);
      const outerSliceY = slice(oY);
      const { x: innerSliceX, y: innerSliceY } = insetEdge(
        outerSliceX,
        outerSliceY,
        slice(x),
        slice(y),
        1.4,
      );
      return toGeometry(
        buildStripGeometry(outerSliceX, outerSliceY, innerSliceX, innerSliceY, origin, 0.035),
      );
    });

    return {
      asphalt,
      innerKerb,
      outerKerb,
      innerLine,
      outerLine,
      line,
      drsZones,
      linePosition: [
        sceneX(x[0], origin),
        0.03,
        sceneZ(y[0], origin),
      ] as [number, number, number],
      lineHeading: heading,
      groundSize: Math.max(bounds.width, bounds.depth) * 4,
    };
  }, [geometry, origin]);

  if (!built) return null;

  return (
    <group>
      <mesh
        geometry={built.asphalt}
        receiveShadow
        renderOrder={1}
      >
        <meshStandardMaterial
          color="#3d434b"
          roughness={0.95}
          metalness={0.04}
          envMapIntensity={0.7}
        />
      </mesh>

      <mesh geometry={built.innerKerb} receiveShadow renderOrder={2}>
        <meshStandardMaterial vertexColors roughness={0.7} metalness={0.02} />
      </mesh>
      <mesh geometry={built.outerKerb} receiveShadow renderOrder={2}>
        <meshStandardMaterial vertexColors roughness={0.7} metalness={0.02} />
      </mesh>

      <mesh geometry={built.innerLine} receiveShadow renderOrder={3}>
        <meshStandardMaterial color="#e2e1d9" roughness={.9} />
      </mesh>
      <mesh geometry={built.outerLine} receiveShadow renderOrder={3}>
        <meshStandardMaterial color="#e2e1d9" roughness={.9} />
      </mesh>

      {built.drsZones.map((zone, index) => (
        <mesh key={index} geometry={zone} renderOrder={4}>
          <meshBasicMaterial color="#2fd46a" transparent opacity={0.5} />
        </mesh>
      ))}

      <mesh
        geometry={built.line}
        position={built.linePosition}
        rotation={[0, built.lineHeading, 0]}
        renderOrder={3}
      >
        <meshStandardMaterial
          color="#f2f4f7"
          roughness={0.9}
        />
      </mesh>

      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -1.5, 0]}
        receiveShadow
      >
        <planeGeometry args={[built.groundSize, built.groundSize]} />
        <meshStandardMaterial
          color="#16211b"
          roughness={1}
          metalness={0}
          envMapIntensity={0.5}
        />
      </mesh>
    </group>
  );
}
