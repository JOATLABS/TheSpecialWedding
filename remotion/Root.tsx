import { Composition, type CalculateMetadataFunction } from 'remotion';

import { DemoVideoComposition } from './DemoVideoComposition';
import type { DemoVideoRemotionProps } from './types';

const defaultProps: DemoVideoRemotionProps = {
  demoId: 'planner-command-center-walkthrough',
  title: 'Planner command center walkthrough',
  audience: 'Professional planners evaluating a connected planner operating system.',
  rawVideoPath: '',
  narrationPath: '',
  captions: [],
  format: 'web-16x9',
  durationSeconds: 90,
};

const calculateMetadata: CalculateMetadataFunction<DemoVideoRemotionProps> = ({ props }) => {
  return {
    durationInFrames: Math.max(30, Math.ceil(props.durationSeconds * 30)),
  };
};

export function RemotionRoot() {
  return (
    <>
      <Composition
        id="DemoVideo16x9"
        component={DemoVideoComposition}
        durationInFrames={360}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{ ...defaultProps, format: 'web-16x9' }}
        calculateMetadata={calculateMetadata}
      />
      <Composition
        id="DemoVideo9x16"
        component={DemoVideoComposition}
        durationInFrames={360}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{ ...defaultProps, format: 'social-9x16' }}
        calculateMetadata={calculateMetadata}
      />
    </>
  );
}
