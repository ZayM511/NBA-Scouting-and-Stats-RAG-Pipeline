"use client";

/**
 * BasketballOrb — the Ball Knowledge Oracle, rendered from a real 3D model.
 *
 * Visual stack (outer → inner):
 *   1. EffectComposer w/ Bloom + Vignette — gives the ball its warm glow
 *      from its own emissive material; no separate aura layer.
 *   2. Sparkles cloud that lives strictly *behind* the ball (z < 0) so it
 *      never crosses in front of the basketball silhouette.
 *   3. The basketball GLB at /basketball_ball.glb, mouse-parallax-tracked
 *      and slowly rotating inside a Float wrapper.
 *
 * The GLB is preloaded at module-eval time so the first render isn't gated
 * on the network.
 */

import { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Sparkles, useGLTF } from "@react-three/drei";
import { EffectComposer, Bloom, Vignette } from "@react-three/postprocessing";
import * as THREE from "three";
import type { PointLight } from "three";

const MODEL_PATH = "/basketball_ball.glb";

useGLTF.preload(MODEL_PATH);

interface OrbProps {
  scale?: number;
  dprMax?: number;
  subdued?: boolean;
  className?: string;
}

export function BasketballOrb({
  scale = 1,
  dprMax = 2,
  subdued = false,
  className,
}: OrbProps) {
  return (
    <div className={className} aria-hidden="true" data-testid="basketball-orb">
      <Canvas
        dpr={[1, dprMax]}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        camera={{ position: [0, 0, 3.4], fov: 38 }}
        style={{ background: "transparent" }}
      >
        <ambientLight intensity={0.45} />
        <directionalLight position={[3, 3, 4]} intensity={1.1} color="#ffe1c4" />
        <directionalLight position={[-3, -1, 2]} intensity={0.45} color="#bfdbfe" />
        <pointLight position={[1.5, 1.2, 2]} intensity={1.5} distance={6} color="#ff9a5a" />
        <pointLight position={[-1.2, -0.8, 1.6]} intensity={1.0} distance={5} color="#7dd3fc" />
        <GoldenPulse />


        <Suspense fallback={null}>
          <Float speed={1.1} rotationIntensity={0.35} floatIntensity={0.55}>
            <group scale={scale}>
              <BasketballModel />
            </group>
          </Float>

          {/* Sparkles live in a thin slab strictly behind the ball.
              position[z] = -2 anchors the spawn box 2 units behind world
              origin; scale[z] = 1.5 keeps the slab thin so even the
              furthest-forward particle (z = -0.5) is still behind the
              ball's front face (≈ z = 1). X/Y stay wide so the field
              feels open. */}
          <Sparkles
            count={48}
            position={[0, 0, -2]}
            scale={[6, 6, 1.5]}
            size={2.4}
            speed={0.35}
            opacity={0.7}
            color="#ffb380"
          />
        </Suspense>

        <EffectComposer multisampling={0}>
          <Bloom
            intensity={subdued ? 0.45 : 0.95}
            luminanceThreshold={0.22}
            luminanceSmoothing={0.85}
            mipmapBlur
          />
          <Vignette eskil={false} offset={0.25} darkness={0.65} />
        </EffectComposer>
      </Canvas>
    </div>
  );
}

/**
 * BasketballModel — loads the GLB, normalizes it to a unit-radius sphere
 * footprint, and applies slow rotation + mouse parallax.
 */
function BasketballModel() {
  const group = useRef<THREE.Group>(null);
  const { scene } = useGLTF(MODEL_PATH);

  const cloned = useMemo(() => {
    const c = scene.clone(true);
    // Auto-fit: scale so the longest bounding-box axis is ~2 units. Lets us
    // swap models without rewiring scale.
    const box = new THREE.Box3().setFromObject(c);
    const size = new THREE.Vector3();
    box.getSize(size);
    const longest = Math.max(size.x, size.y, size.z) || 1;
    const fit = 2.0 / longest;
    c.scale.setScalar(fit);
    // Recenter so the ball spins around its own middle.
    const center = new THREE.Vector3();
    box.getCenter(center).multiplyScalar(fit);
    c.position.sub(center);
    // Tiny material tweak so the ball reads warm even in the dark scene.
    c.traverse((obj) => {
      const m = (obj as THREE.Mesh).material as THREE.MeshStandardMaterial | undefined;
      if (m && "emissive" in m) {
        m.emissive = new THREE.Color("#3a1300");
        m.emissiveIntensity = 0.15;
      }
    });
    return c;
  }, [scene]);

  useFrame((_, delta) => {
    const g = group.current;
    if (!g) return;
    g.rotation.y += delta * 0.28;
    g.rotation.x += delta * 0.07;
  });

  return (
    <group ref={group}>
      <primitive object={cloned} />
    </group>
  );
}

/**
 * GoldenPulse — slow-breathing ambient point light in front of the ball
 * that swings between dim and bright over a ~6 s sine wave. Adds a
 * gentle, never-distracting "this thing is alive" warmth without any
 * geometry or shaders. The bloom pass turns the bright peaks into a
 * golden halo at the ball's silhouette.
 */
function GoldenPulse() {
  const lightRef = useRef<PointLight>(null);
  const phase = useRef(0);
  useFrame((_, delta) => {
    if (!lightRef.current) return;
    phase.current += delta;
    // Sine in [0,1], then map to [1.2 .. 3.4] intensity range.
    const t = (Math.sin(phase.current * (2 * Math.PI) / 6) + 1) / 2;
    lightRef.current.intensity = 1.2 + t * 2.2;
  });
  return (
    <pointLight
      ref={lightRef}
      position={[0, 0, 2.2]}
      color="#ffd27a"
      distance={7}
      decay={1.6}
    />
  );
}
