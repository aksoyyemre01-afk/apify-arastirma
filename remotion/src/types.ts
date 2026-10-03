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
  // Yalnızca uzun videoda (4 sn'den uzun sahneler); short'larda yok.
  accents?: Accent[];
};
type SceneBaseLong = SceneBase;

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
  | QuoteScene
  | PhotoScene
  | ChapterScene
  | KeywordScene;

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
    // volume: efekt başına, seslendirmeye göre ölçülmüş kazanç (src/scene_planner.py _sfx_gain).
    sfx: {src: string; from: number; volume?: number}[];
  };
  outro: Outro | null;
};

// ---------------------------------------------------------------- uzun video (1920x1080)
// Uzun sahnelerde her 3-4 sn'de bir giren vurgu: `at` sahneye göre kare.
export type Accent = {at: number; text: string};
export type PhotoRef = {name: string; src: string; focus?: string};
export type PhotoScene = SceneBaseLong & {type: 'photo'; photo: PhotoRef | null};
export type ChapterScene = SceneBaseLong & {type: 'chapter'; title: string};
// Anahtar kelime kartı (yalnız uzun video): o an söylenen 1-3 kelime, sol hizalı, tırnaksız.
export type KeywordScene = SceneBaseLong & {type: 'keyword'; text: string};

export type ThumbnailProps = {
  width: number;
  height: number;
  theme: Theme;
  value: string;
  unit: string;
  headline: string;
  logo: LogoRef | null;
  tone: Tone;
};
