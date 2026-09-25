import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {Counter, Label, LogoCard, SceneFrame, fitFont} from './components';
import {BODY, HEADING, LAYOUT} from './theme';
import {useTheme} from './theme';
import {
  BigNumberScene,
  ChartScene,
  ComparisonScene,
  LogoIntroScene,
  QuoteScene,
  SceneProps,
  TimelineScene,
} from './types';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const CONTENT_W = 1080 - LAYOUT.sidePadding * 2;

// Çip varsa sahnenin ana gövdesi çiplerin altından başlar.
const Body: React.FC<{hasChips: boolean; children: React.ReactNode; gap?: number}> = ({hasChips, children, gap = 44}) => (
  <div
    style={{
      position: 'absolute',
      top: hasChips ? LAYOUT.contentTopWithChips : LAYOUT.contentTop,
      bottom: 1920 - LAYOUT.contentBottom,
      left: LAYOUT.sidePadding,
      right: LAYOUT.sidePadding,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap,
    }}
  >
    {children}
  </div>
);

const Pop: React.FC<{delay?: number; children: React.ReactNode; style?: React.CSSProperties}> = ({delay = 0, children, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: frame - delay, fps, config: {damping: 11, mass: 0.6}});
  // Yarı boyuttan başlar: sahne geçişlerinde ekran birkaç kare boyunca boş kalmaz.
  return (
    <div style={{transform: `scale(${interpolate(s, [0, 1], [0.55, 1])})`, opacity: Math.min(1, 0.3 + s * 1.2), ...style}}>
      {children}
    </div>
  );
};

// Kelime kelime beliren metin; highlight kelimeleri vurgu kutusu alır.
const StaggerText: React.FC<{
  text: string;
  size: number;
  highlight?: string[];
  delay?: number;
  weight?: number;
  font?: string;
}> = ({text, size, highlight = [], delay = 0, weight = 800, font = HEADING}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {palette} = useTheme();
  const norm = (w: string) => w.toLocaleLowerCase('tr').replace(/[^\p{L}\p{N}]/gu, '');
  const hl = new Set(highlight.flatMap((h) => h.split(/\s+/)).map(norm));
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <div lang="tr" style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: `${size * 0.18}px ${size * 0.26}px`, maxWidth: CONTENT_W}}>
      {words.map((w, i) => {
        const s = spring({frame: frame - delay - i * 3, fps, config: {damping: 13}});
        const isHl = hl.has(norm(w));
        const wipe = interpolate(frame - delay - i * 3 - 6, [0, 8], [0, 100], clamp);
        return (
          <span
            key={i}
            style={{
              fontFamily: font,
              fontWeight: weight,
              fontSize: size,
              lineHeight: 1.12,
              color: isHl ? palette.card_text : palette.text,
              padding: isHl ? `0 ${size * 0.16}px` : 0,
              borderRadius: size * 0.14,
              background: isHl
                ? `linear-gradient(90deg, ${palette.accent} ${wipe}%, transparent ${wipe}%)`
                : 'transparent',
              transform: `translateY(${(1 - s) * 40}px)`,
              opacity: s,
              display: 'inline-block',
            }}
          >
            {w}
          </span>
        );
      })}
    </div>
  );
};

// ---------------------------------------------------------------- logo_intro
const LogoIntro: React.FC<{s: LogoIntroScene}> = ({s}) => {
  const frame = useCurrentFrame();
  const sweep = interpolate(frame, [6, 30], [-60, 160], clamp);
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <Body hasChips={s.chips.length > 0} gap={60}>
        {s.logo ? (
          <div style={{position: 'relative'}}>
            <LogoCard logo={s.logo} width={800} height={440} />
            <div
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: 60,
                background: `linear-gradient(105deg, transparent ${sweep - 20}%, rgba(255,255,255,0.55) ${sweep}%, transparent ${sweep + 20}%)`,
                mixBlendMode: 'overlay',
                pointerEvents: 'none',
              }}
            />
          </div>
        ) : null}
      </Body>
      <Label text={s.label} top={1060} size={s.variant > 0 ? 68 : 60} />
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- big_number
const BigNumber: React.FC<{s: BigNumberScene}> = ({s}) => {
  const {palette} = useTheme();
  const numberSize = fitFont(s.value, CONTENT_W, 300, 0.64);
  const unitSize = fitFont(s.unit, CONTENT_W, 118, 0.7);
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <Body hasChips={s.chips.length > 0} gap={10}>
        <Pop>
          <div
            style={{
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: numberSize,
              lineHeight: 1,
              color: palette.text,
              textShadow: `0 0 60px ${palette.accent}55`,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            <Counter value={s.value} animate={s.variant === 0} />
          </div>
        </Pop>
        {s.unit ? (
          <Pop delay={6}>
            <div lang="tr" style={{fontFamily: HEADING, fontWeight: 900, fontSize: unitSize, color: palette.accent, letterSpacing: 2}}>
              {s.unit}
            </div>
          </Pop>
        ) : null}
      </Body>
      <Label text={s.label} top={1060} size={s.variant > 0 ? 68 : 58} delay={s.variant > 0 ? 0 : 12} />
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- comparison
const Comparison: React.FC<{s: ComparisonScene}> = ({s}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {palette} = useTheme();
  const vs = spring({frame: frame - 8, fps, config: {damping: 9}});
  const hlOn = s.variant > 0 || frame > 20;
  const card = (ref: ComparisonScene['left'], value: string, side: 'left' | 'right') => {
    const enter = spring({frame: frame - (side === 'left' ? 0 : 4), fps, config: {damping: 14}});
    const isHl = s.highlight === side;
    const dim = hlOn && s.highlight !== '' && !isHl;
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 34,
          transform: `translateX(${(1 - enter) * (side === 'left' ? -500 : 500)}px) scale(${hlOn && isHl ? 1.07 : 1})`,
        }}
      >
        {ref ? <LogoCard logo={ref} width={340} height={220} dim={dim} /> : <div style={{width: 340, height: 220}} />}
        {value ? (
          <div
            lang="tr"
            style={{
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: fitFont(value, 340, 60, 0.66),
              color: hlOn && isHl ? palette.accent : palette.text,
              opacity: dim ? 0.5 : 1,
              textAlign: 'center',
            }}
          >
            {value}
          </div>
        ) : null}
      </div>
    );
  };
  const focusX = s.variant > 0 && s.highlight ? (s.highlight === 'left' ? 380 : 700) : 540;
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} focus={{x: focusX, y: 700}} chips={s.chips}>
      <Body hasChips={s.chips.length > 0} gap={70}>
        {s.label ? <StaggerText text={s.label} size={62} weight={800} /> : null}
        <div style={{display: 'flex', alignItems: 'flex-start', justifyContent: 'center', gap: 20, width: 1080}}>
          {card(s.left, s.leftValue, 'left')}
          <div
            style={{
              alignSelf: 'flex-start',
              marginTop: 45,
              width: 120,
              height: 120,
              borderRadius: 120,
              background: palette.accent,
              color: palette.card_text,
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: 54,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transform: `scale(${vs}) rotate(${(1 - vs) * -90}deg)`,
              flexShrink: 0,
            }}
          >
            VS
          </div>
          {card(s.right, s.rightValue, 'right')}
        </div>
      </Body>
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- timeline
const Timeline: React.FC<{s: TimelineScene}> = ({s}) => {
  const frame = useCurrentFrame();
  const {palette} = useTheme();
  const draw = interpolate(frame, [0, 22], [0, 100], clamp);
  const dotPulse = 1 + Math.sin(frame / 4) * 0.12;
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <Body hasChips={s.chips.length > 0} gap={50}>
        <Pop>
          <div style={{fontFamily: HEADING, fontWeight: 900, fontSize: fitFont(s.year, CONTENT_W, 250, 0.66), color: palette.accent, lineHeight: 1}}>
            <Counter value={s.year} animate={s.variant === 0} durationInFrames={22} />
          </div>
        </Pop>
        <div style={{position: 'relative', width: CONTENT_W, height: 60}}>
          <div style={{position: 'absolute', top: 26, left: 0, height: 8, width: `${draw}%`, background: `${palette.text}55`, borderRadius: 8}} />
          {[0.1, 0.3, 0.7, 0.9].map((p) => (
            <div key={p} style={{position: 'absolute', top: 18, left: `${p * 100}%`, width: 4, height: 24, background: `${palette.text}44`, opacity: draw / 100 > p ? 1 : 0}} />
          ))}
          <div
            style={{
              position: 'absolute',
              top: 30 - 28,
              left: `calc(50% - 28px)`,
              width: 56,
              height: 56,
              borderRadius: 56,
              background: palette.accent,
              boxShadow: `0 0 0 ${14 * dotPulse}px ${palette.accent}33`,
              transform: `scale(${draw >= 50 ? dotPulse : 0})`,
            }}
          />
        </div>
        {s.text ? <StaggerText text={s.text} size={s.variant > 0 ? 76 : 68} delay={10} weight={700} font={BODY} /> : null}
      </Body>
      <Label text={s.label} top={1080} />
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- chart
const Chart: React.FC<{s: ChartScene}> = ({s}) => {
  const frame = useCurrentFrame();
  const {palette} = useTheme();
  const color = s.direction === 'down' ? palette.down : palette.up;
  const W = CONTENT_W;
  const H = 560;
  const pad = 40;
  const min = Math.min(...s.points);
  const max = Math.max(...s.points);
  const range = max - min || 1;
  const pts = s.points.map((v, i) => ({
    x: pad + (i / (s.points.length - 1)) * (W - pad * 2),
    y: pad + (1 - (v - min) / range) * (H - pad * 2),
  }));
  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const area = `${path} L${pts[pts.length - 1].x},${H} L${pts[0].x},${H} Z`;
  const progress = s.variant > 0 ? 1 : interpolate(frame, [4, 34], [0, 1], clamp);
  const end = pts[pts.length - 1];
  const endShown = progress >= 0.98;
  const arrow = s.direction === 'down' ? '▼' : '▲';
  const bodyTop = s.chips.length ? LAYOUT.contentTopWithChips : LAYOUT.contentTop;
  const chartTop = bodyTop + 150;
  return (
    <SceneFrame
      durationInFrames={s.durationInFrames}
      variant={s.variant}
      focus={{x: LAYOUT.sidePadding + end.x, y: chartTop + end.y}}
      chips={s.chips}
    >
      <div
        style={{
          position: 'absolute',
          top: bodyTop + 20,
          left: LAYOUT.sidePadding,
          right: LAYOUT.sidePadding,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 24,
        }}
      >
        {s.label ? <span style={{fontSize: 70, color, fontFamily: HEADING, fontWeight: 900}}>{arrow}</span> : null}
        {s.label ? (
          <span lang="tr" style={{fontFamily: HEADING, fontWeight: 800, fontSize: fitFont(s.label, CONTENT_W - 120, 62, 0.6), color: palette.text}}>
            {s.label}
          </span>
        ) : null}
      </div>
      <svg width={W} height={H + 70} style={{position: 'absolute', top: chartTop, left: LAYOUT.sidePadding, overflow: 'visible'}}>
        <defs>
          <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.45} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
          <clipPath id="reveal">
            <rect x={0} y={-50} width={W * progress + 10} height={H + 100} />
          </clipPath>
        </defs>
        {[0.25, 0.5, 0.75].map((g) => (
          <line key={g} x1={0} x2={W} y1={H * g} y2={H * g} stroke={palette.text} strokeOpacity={0.08} strokeWidth={3} />
        ))}
        <path d={area} fill="url(#area)" clipPath="url(#reveal)" />
        <path d={path} fill="none" stroke={color} strokeWidth={14} strokeLinecap="round" strokeLinejoin="round" clipPath="url(#reveal)" />
        {pts.map((p, i) => {
          const visible = progress >= i / (pts.length - 1) - 0.01;
          return visible ? <circle key={i} cx={p.x} cy={p.y} r={i === pts.length - 1 ? 20 + Math.sin(frame / 4) * 4 : 11} fill={i === pts.length - 1 ? color : palette.text} /> : null;
        })}
        {s.pointLabels.map((l, i) => (
          <text key={i} x={pts[i].x} y={H + 58} fill={palette.muted} fontFamily={BODY} fontWeight={700} fontSize={36} textAnchor="middle" opacity={progress >= i / (pts.length - 1) - 0.01 ? 1 : 0}>
            {l}
          </text>
        ))}
      </svg>
      {s.endValue && endShown ? (
        <div
          lang="tr"
          style={{
            position: 'absolute',
            top: Math.max(chartTop + end.y - 150, bodyTop + 110),
            right: LAYOUT.sidePadding - 10,
            background: color,
            color: '#FFFFFF',
            fontFamily: HEADING,
            fontWeight: 900,
            fontSize: fitFont(s.endValue, 560, s.variant > 0 ? 76 : 64, 0.66),
            padding: '14px 30px',
            borderRadius: 26,
            boxShadow: '0 20px 50px rgba(0,0,0,0.4)',
            transform: `scale(${s.variant > 0 ? 1 : interpolate(frame, [34, 42], [0.4, 1], clamp)})`,
            transformOrigin: 'right center',
          }}
        >
          {s.endValue}
        </div>
      ) : null}
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- quote
const Quote: React.FC<{s: QuoteScene}> = ({s}) => {
  const {palette} = useTheme();
  const words = s.text.split(/\s+/).length;
  const size = words <= 4 ? 110 : words <= 7 ? 92 : 80;
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <Body hasChips={s.chips.length > 0} gap={30}>
        <div style={{fontFamily: HEADING, fontWeight: 900, fontSize: 200, lineHeight: 0.6, color: palette.accent, opacity: 0.9, height: 90}}>“</div>
        <StaggerText text={s.text} size={size} highlight={s.highlight} delay={s.variant > 0 ? -30 : 0} />
      </Body>
      <Label text={s.label} top={1080} />
    </SceneFrame>
  );
};

export const SceneView: React.FC<{scene: SceneProps}> = ({scene}) => {
  switch (scene.type) {
    case 'logo_intro':
      return <LogoIntro s={scene} />;
    case 'big_number':
      return <BigNumber s={scene} />;
    case 'comparison':
      return <Comparison s={scene} />;
    case 'timeline':
      return <Timeline s={scene} />;
    case 'chart':
      return <Chart s={scene} />;
    case 'quote':
      return <Quote s={scene} />;
    default:
      return <AbsoluteFill />;
  }
};
