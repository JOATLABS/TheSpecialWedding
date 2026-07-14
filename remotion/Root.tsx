import { Composition, type CalculateMetadataFunction } from 'remotion';

import { DemoVideoComposition } from './DemoVideoComposition';
import type { DemoVideoRemotionProps } from './types';

const websiteDefaultProps: DemoVideoRemotionProps = {
  demoId: 'planner-command-center-walkthrough',
  title: 'Planner command center walkthrough',
  audience: 'Professional planners evaluating a connected planner operating system.',
  rawVideoPath: '',
  narrationPath: '',
  format: 'web-16x9',
  durationSeconds: 90,
};

const socialDefaultProps: DemoVideoRemotionProps = {
  demoId: 'connection-over-tools-social',
  title: 'One plan. Three clear views.',
  audience: 'Wedding planners replacing disconnected planner, couple, and guest tools.',
  rawVideoPath: '',
  narrationPath: '',
  format: 'social-9x16',
  durationSeconds: 30,
  phaseOnePillar: 'Connection Over Tools',
  socialOutcome: 'Keep planner, couple, and guest context connected without exposing planner controls.',
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
        defaultProps={websiteDefaultProps}
        calculateMetadata={calculateMetadata}
      />
      <Composition
        id="DemoVideo9x16"
        component={DemoVideoComposition}
        durationInFrames={360}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={socialDefaultProps}
        calculateMetadata={calculateMetadata}
      />
    </>
  );
}
