// Python tarafı (src/scene_planner.py) bu yapıyı props.json olarak üretir.

export type Palette = {
  background: string;
  background_alt: string;
  text: string;
  muted: string;
  accent: string;
  up: string;
  down: string;
  card: string;
  card_text: string;
};

export type Theme = {
  palette: Palette;
  headingFont: string;
  bodyFont: string;
  badgeText: string;
  intro: boolean;
};

export type LogoRef = {
  name: string;
  src: string | null;
  hidden: boolean;
  // Sahneye göre kare; gizli kutu bu karede logoya dönüşür.
  revealAt: number | null;
};

// Sahnenin duygusal yönü; zemin tonunu belirler (yükseliş yeşilimsi, düşüş kırmızımsı).
export type Tone = 'rise' | 'fall' | 'neutral';

type SceneBase = {
  from: number;
  durationInFrames: number;
  variant: number;
  label: string;
  chips: LogoRef[];
  tone: Tone;
};

export type LogoIntroScene = SceneBase & {type: 'logo_intro'; logo: LogoRef | null};
export type BigNumberScene = SceneBase & {type: 'big_number'; value: string; unit: string};
export type ComparisonScene = SceneBase & {
  type: 'comparison';
  left: LogoRef | null;
  right: LogoRef | null;
  leftValue: string;
  rightValue: string;
  highlight: '' | 'left' | 'right';
};
export type TimelineScene = SceneBase & {type: 'timeline'; year: string; text: string};
export type ChartScene = SceneBase & {
  type: 'chart';
  points: number[];
  pointLabels: string[];
  direction: 'up' | 'down';
  endValue: string;
};
export type QuoteScene = SceneBase & {type: 'quote'; text: string; highlight: string[]};

export type SceneProps =
  | LogoIntroScene
  | BigNumberScene
  | ComparisonScene
  | TimelineScene
  | ChartScene
  | QuoteScene;

export type CaptionPage = {
  from: number;
  durationInFrames: number;
  words: {text: string; start: number; end: number}[];
};

export type Outro = {
  from: number;
  durationInFrames: number;
  cta: string;
  seriesName: string;
  followText: string;
  partText: string;
};

export type ShortProps = {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  theme: Theme;
  scenes: SceneProps[];
  captions: CaptionPage[];
  audio: {
    narration: string | null;
    music: string | null;
    musicVolume: number;
    sfxVolume: number;
    sfx: {src: string; from: number}[];
  };
  outro: Outro | null;
};
