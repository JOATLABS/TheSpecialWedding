import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { MeshDistortMaterial, Sphere, Environment, Float } from '@react-three/drei';
import * as THREE from 'three';

function LiquidSphere() {
  const mesh = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (mesh.current) {
      // Subtle rotation
      mesh.current.rotation.x = state.clock.getElapsedTime() * 0.1;
      mesh.current.rotation.y = state.clock.getElapsedTime() * 0.15;
    }
  });

  return (
    <Float speed={1.5} rotationIntensity={0.5} floatIntensity={0.5}>
      <Sphere args={[1, 64, 64]} ref={mesh} scale={[2, 2, 2]}>
        <MeshDistortMaterial
          color="#e0e7ff" // Very light indigo/white for liquid mirror look
          attach="material"
          distort={0.4} // Liquid distortion amount
          speed={1.5} // Speed of distortion
          roughness={0.1}
          metalness={0.9} // High metalness for mirror look
          envMapIntensity={1}
        />
      </Sphere>
    </Float>
  );
}

function Scene() {
  // Mouse interaction for light position?
  // For now, static beautiful lighting
  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 5]} intensity={1} color="#ffffff" />
      <pointLight position={[-10, -10, -10]} intensity={0.5} color="#3b82f6" />

      <LiquidSphere />

      <Environment preset="city" />
    </>
  );
}

export function LiquidBackground() {
  return (
    <div className="absolute inset-0 w-full h-full pointer-events-none -z-10 bg-gradient-to-br from-slate-50 to-slate-100">
      <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
        <Scene />
      </Canvas>

      {/* Frosted glass overlay to ensure text legibility if needed,
          but we want the mirror to be visible.
          Maybe a vignette? */}
      <div className="absolute inset-0 bg-white/30 backdrop-blur-[2px]" />
    </div>
  );
}
