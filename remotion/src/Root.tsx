import React from 'react';
import {CalculateMetadataFunction, Composition} from 'remotion';
import {Short} from './Short';
import {ShortProps} from './types';

const calculateMetadata: CalculateMetadataFunction<ShortProps> = ({props}) => ({
  durationInFrames: Math.max(props.durationInFrames, 1),
  fps: props.fps,
  width: props.width,
  height: props.height,
});

// Gerçek içerik her zaman --props=props.json ile gelir; bu varsayılan yalnızca
// Remotion Studio'nun boş açılabilmesi içindir (kanala/konuya özgü hiçbir şey yok).
const defaultProps: ShortProps = {
  fps: 30,
  width: 1080,
  height: 1920,
  durationInFrames: 90,
  theme: {
    palette: {
      background: '#0B1020',
      background_alt: '#18204A',
      text: '#FFFFFF',
      muted: '#A9B1D6',
      accent: '#FFC61A',
      up: '#22C55E',
      down: '#FF3B3B',
      card: '#FFFFFF',
      card_text: '#0B1020',
    },
    headingFont: '',
    bodyFont: '',
    badgeText: '',
    intro: false,
  },
  scenes: [],
  captions: [],
  audio: {narration: null, music: null, musicVolume: 0.1, sfxVolume: 0.5, sfx: []},
  outro: null,
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Short"
    component={Short}
    defaultProps={defaultProps}
    calculateMetadata={calculateMetadata}
    durationInFrames={90}
    fps={30}
    width={1080}
    height={1920}
  />
);
