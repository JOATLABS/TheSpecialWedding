import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import * as React from 'react';
import CrazyGLWrapper, { useContent, useHeroReady, } from '@crazygl/core';
import metadata from './metadata.json';
import '@crazygl/core/style.css';
import './style.css';
/* ─────────────────────────────────────────────────────────────────────────
... physics comment truncated for brevity ...
   ───────────────────────────────────────────────────────────────────────── */
const StackStage = React.lazy(() => import('./StackStage'));
function CardStackHero(props) {
    const { size, input, seed, reducedMotion, rootRef, 
    // Screenshots array support
    screenshots: propScreenshots,
    // Screenshots fallback
    screenshot1 = 'https://crazygl.com/samples/screenshot-dashboard-dark.avif', screenshot2 = 'https://crazygl.com/samples/screenshot-dashboard-dark-2.avif', screenshot3 = 'https://crazygl.com/samples/screenshot-video-editor-dark.avif', screenshot4 = 'https://crazygl.com/samples/screenshot-dashboard-light.avif', screenshot5 = 'https://crazygl.com/samples/screenshot-video-editor-light.avif', 
    // Stack
    cardCount = propScreenshots ? propScreenshots.length : 5, stackOffsetX = 0.06, stackOffsetY = 0.04, stackOffsetZ = 0.04, cardSize = 2.4, groupOffsetX = 0, groupOffsetY = 0, cardCornerRadius = 0.07, 
    // Flip cycle
    flipCycle = true, cycleInterval = 3.5, 
    // Hover
    fanDistance = 0.25, fanRotation = 0.04, springStiffness = 180, springDamping = 14, 
    // Motion
    cursorTilt = 0.7, ambientFloat = 0.35, 
    // Style
    edgeGlowColor = '#56e3ff', edgeGlowStrength = 0.5, shadowStrength = 0.55, 
    // Lighting
    keyColor = '#ffffff', fillColor = '#a0bcff', screenBrightness = 0.4, 
    // Layout
    contentAlign = 'start', paddingX = 64, paddingY = 48, 
    // Background
    bgTop = '#161a24', bgBottom = '#06080d', } = props;
    const content = useContent(props);
    useHeroReady(props);
    const [mounted, setMounted] = React.useState(false);
    React.useEffect(() => setMounted(true), []);
    const align = contentAlign === 'end'
        ? { justifyContent: 'flex-end', textAlign: 'right' }
        : contentAlign === 'center'
            ? { justifyContent: 'center', textAlign: 'center' }
            : { justifyContent: 'flex-start', textAlign: 'left' };
    const screenshots = React.useMemo(() => propScreenshots || [screenshot1, screenshot2, screenshot3, screenshot4, screenshot5], [propScreenshots, screenshot1, screenshot2, screenshot3, screenshot4, screenshot5]);
    return (_jsxs(_Fragment, { children: [_jsx("crazygl-stage", { style: {
                    position: 'absolute',
                    inset: 0,
                    zIndex: 0,
                    overflow: 'hidden',
                    background: `linear-gradient(180deg, ${bgTop} 0%, ${bgBottom} 100%)`,
                }, children: mounted ? (_jsx(React.Suspense, { fallback: null, children: _jsx(StackStage, { rootRef: rootRef, size: size, input: input, seed: seed, reducedMotion: reducedMotion, screenshots: screenshots, cardCount: cardCount, stackOffsetX: stackOffsetX, stackOffsetY: stackOffsetY, stackOffsetZ: stackOffsetZ, cardSize: cardSize, groupOffsetX: groupOffsetX, groupOffsetY: groupOffsetY, cardCornerRadius: cardCornerRadius, flipCycle: flipCycle, cycleInterval: cycleInterval, fanDistance: fanDistance, fanRotation: fanRotation, springStiffness: springStiffness, springDamping: springDamping, cursorTilt: cursorTilt, ambientFloat: ambientFloat, edgeGlowColor: edgeGlowColor, edgeGlowStrength: edgeGlowStrength, shadowStrength: shadowStrength, keyColor: keyColor, fillColor: fillColor, screenBrightness: screenBrightness }) })) : null }), _jsx("crazygl-content", { style: {
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    zIndex: 1,
                    pointerEvents: 'none',
                    padding: `${paddingY}px ${paddingX}px`,
                    ...align,
                }, children: _jsx("div", { className: "crazygl-cs-content", children: content.node }) })] }));
}
export { metadata };
export default function CardStack(props) {
    return _jsx(CrazyGLWrapper, { hero: CardStackHero, metadata: metadata, ...props });
}
