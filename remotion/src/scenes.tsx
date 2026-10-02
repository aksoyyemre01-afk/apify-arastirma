import React from 'react';
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Counter, EASE_IN_OUT, Label, LogoCard, MOVING, SceneFrame, enterProgress, fitFont, px} from './components';
import {BODY, HEADING, Layout, sz, useLayout} from './theme';
import {useTheme} from './theme';
import {
  Accent,
  BigNumberScene,
  ChapterScene,
  ChartScene,
  ComparisonScene,
  LogoIntroScene,
  PhotoScene,
  QuoteScene,
  SceneProps,
  TimelineScene,
} from './types';

// Titreme önleme (bkz. components.tsx): bu dosyada scale/rotate yok; tüm hareket opacity
// ve tam piksele yuvarlanmış translate ile, konumlar tam piksel, easing'ler yumuşak.

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const contentW = (L: Layout) => L.width - L.sidePadding * 2;

// Çip varsa sahnenin ana gövdesi çiplerin altından başlar.
const Body: React.FC<{hasChips: boolean; children: React.ReactNode; gap?: number}> = ({hasChips, children, gap = 44}) => {
  const LAYOUT = useLayout();
  return (
    <div
      style={{
        position: 'absolute',
        top: hasChips ? LAYOUT.contentTopWithChips : LAYOUT.contentTop,
        bottom: LAYOUT.height - LAYOUT.contentBottom,
        left: LAYOUT.sidePadding,
        right: LAYOUT.sidePadding,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: sz(LAYOUT, gap),
      }}
    >
      {children}
    </div>
  );
};

// Giriş: yarı saydamdan tam görünüre ve 40 px aşağıdan yerine (ölçekleme yok).
const Pop: React.FC<{delay?: number; children: React.ReactNode}> = ({delay = 0, children}) => {
  const frame = useCurrentFrame();
  const L = useLayout();
  const s = enterProgress(frame, delay, 12);
  return (
    <div style={{opacity: 0.3 + 0.7 * s, transform: `translateY(${px((1 - s) * sz(L, 40))}px)`, ...MOVING}}>{children}</div>
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
  const {palette} = useTheme();
  const L = useLayout();
  size = sz(L, size);
  const norm = (w: string) => w.toLocaleLowerCase('tr').replace(/[^\p{L}\p{N}]/gu, '');
  const hl = new Set(highlight.flatMap((h) => h.split(/\s+/)).map(norm));
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <div lang="tr" style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: `${px(size * 0.18)}px ${px(size * 0.26)}px`, maxWidth: contentW(L)}}>
      {words.map((w, i) => {
        const s = enterProgress(frame, delay + i * 3, 12);
        const isHl = hl.has(norm(w));
        const wipe = px(interpolate(frame - delay - i * 3 - 6, [0, 8], [0, 100], {...clamp, easing: EASE_IN_OUT}));
        return (
          <span
            key={i}
            style={{
              fontFamily: font,
              fontWeight: weight,
              fontSize: size,
              lineHeight: 1.12,
              color: isHl ? palette.card_text : palette.text,
              padding: isHl ? `0 ${px(size * 0.16)}px` : 0,
              borderRadius: px(size * 0.14),
              background: isHl ? `linear-gradient(90deg, ${palette.accent} ${wipe}%, transparent ${wipe}%)` : 'transparent',
              transform: `translateY(${px((1 - s) * sz(L, 40))}px)`,
              opacity: s,
              display: 'inline-block',
              ...MOVING,
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
  const L = useLayout();
  const sweep = px(interpolate(frame, [6, 30], [-60, 160], {...clamp, easing: EASE_IN_OUT}));
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <Body hasChips={s.chips.length > 0} gap={60}>
        {s.logo ? (
          <div style={{position: 'relative'}}>
            <LogoCard logo={s.logo} width={sz(L, 800)} height={sz(L, 440)} />
            <div
              style={{
                position: 'absolute',
                inset: 0,
                borderRadius: sz(L, 60),
                background: `linear-gradient(105deg, transparent ${sweep - 20}%, rgba(255,255,255,0.55) ${sweep}%, transparent ${sweep + 20}%)`,
                mixBlendMode: 'overlay',
                pointerEvents: 'none',
              }}
            />
          </div>
        ) : null}
      </Body>
      <Label text={s.label} top={L.labelTop} size={s.variant > 0 ? 68 : 60} />
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- big_number
const BigNumber: React.FC<{s: BigNumberScene}> = ({s}) => {
  const {palette} = useTheme();
  const L = useLayout();
  const numberSize = fitFont(s.value, contentW(L), sz(L, 300), 0.64);
  const unitSize = fitFont(s.unit, contentW(L), sz(L, 118), 0.7);
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
              textShadow: `0 0 ${sz(L, 60)}px ${palette.accent}55`,
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
      <Label text={s.label} top={L.labelTop} size={s.variant > 0 ? 68 : 58} delay={s.variant > 0 ? 0 : 12} />
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- comparison
const Comparison: React.FC<{s: ComparisonScene}> = ({s}) => {
  const frame = useCurrentFrame();
  const {palette} = useTheme();
  const L = useLayout();
  const vs = enterProgress(frame, 8, 10);
  const hlOn = s.variant > 0 || frame > 20;
  const card = (ref: ComparisonScene['left'], value: string, side: 'left' | 'right') => {
    const enter = enterProgress(frame, side === 'left' ? 0 : 4, 14);
    const isHl = s.highlight === side;
    const dim = hlOn && s.highlight !== '' && !isHl;
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: sz(L, 34),
          transform: `translateX(${px((1 - enter) * (side === 'left' ? -500 : 500))}px)`,
          ...MOVING,
        }}
      >
        {ref ? (
          <LogoCard logo={ref} width={sz(L, 340)} height={sz(L, 220)} dim={dim} highlight={hlOn && isHl} />
        ) : (
          <div style={{width: sz(L, 340), height: sz(L, 220)}} />
        )}
        {value ? (
          <div
            lang="tr"
            style={{
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: fitFont(value, sz(L, 340), sz(L, 60), 0.66),
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
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <Body hasChips={s.chips.length > 0} gap={70}>
        {s.label ? <StaggerText text={s.label} size={62} weight={800} /> : null}
        <div style={{display: 'flex', alignItems: 'flex-start', justifyContent: 'center', gap: L.scale === 1 ? 20 : sz(L, 120), width: L.scale === 1 ? 1080 : contentW(L)}}>
          {card(s.left, s.leftValue, 'left')}
          <div
            style={{
              alignSelf: 'flex-start',
              marginTop: sz(L, 45),
              width: sz(L, 120),
              height: sz(L, 120),
              borderRadius: sz(L, 120),
              background: palette.accent,
              color: palette.card_text,
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: sz(L, 54),
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: vs,
              transform: `translateY(${px((1 - vs) * 30)}px)`,
              flexShrink: 0,
              ...MOVING,
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
  const L = useLayout();
  const CONTENT_W = contentW(L);
  const draw = interpolate(frame, [0, 22], [0, 1], {...clamp, easing: EASE_IN_OUT});
  const lineW = px(CONTENT_W * draw);
  // Nabız, noktanın boyutuyla değil etrafındaki halkanın parlaklığıyla verilir.
  const ring = 0.12 + (Math.sin(frame / 4) + 1) * 0.1;
  const dotOn = enterProgress(frame, 11, 8);
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <Body hasChips={s.chips.length > 0} gap={50}>
        <Pop>
          <div
            style={{
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: fitFont(s.year, CONTENT_W, sz(L, 250), 0.66),
              color: palette.accent,
              lineHeight: 1,
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            <Counter value={s.year} animate={s.variant === 0} durationInFrames={22} />
          </div>
        </Pop>
        <div style={{position: 'relative', width: CONTENT_W, height: 60}}>
          <div style={{position: 'absolute', top: 26, left: 0, height: 8, width: lineW, background: `${palette.text}55`, borderRadius: 8}} />
          {[0.1, 0.3, 0.7, 0.9].map((p) => (
            <div
              key={p}
              style={{position: 'absolute', top: 18, left: px(CONTENT_W * p), width: 4, height: 24, background: `${palette.text}44`, opacity: draw > p ? 1 : 0}}
            />
          ))}
          <div
            style={{
              position: 'absolute',
              top: 2,
              left: px(CONTENT_W / 2) - 28,
              width: 56,
              height: 56,
              borderRadius: 56,
              background: palette.accent,
              boxShadow: `0 0 0 14px ${palette.accent}${px(ring * 255).toString(16).padStart(2, '0')}`,
              opacity: dotOn,
            }}
          />
        </div>
        {s.text ? <StaggerText text={s.text} size={s.variant > 0 ? 76 : 68} delay={10} weight={700} font={BODY} /> : null}
      </Body>
      <Label text={s.label} top={L.labelTopLow} />
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- chart
const Chart: React.FC<{s: ChartScene}> = ({s}) => {
  const frame = useCurrentFrame();
  const {palette} = useTheme();
  const color = s.direction === 'down' ? palette.down : palette.up;
  const LAYOUT = useLayout();
  const CONTENT_W = contentW(LAYOUT);
  const W = CONTENT_W;
  const H = LAYOUT.chartHeight;
  const pad = 40;
  const min = Math.min(...s.points);
  const max = Math.max(...s.points);
  const range = max - min || 1;
  // Tam piksel koordinatlar: çizgi kenarları kareden kareye aynı piksellere oturur.
  const pts = s.points.map((v, i) => ({
    x: px(pad + (i / (s.points.length - 1)) * (W - pad * 2)),
    y: px(pad + (1 - (v - min) / range) * (H - pad * 2)),
  }));
  const path = pts.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ');
  const area = `${path} L${pts[pts.length - 1].x},${H} L${pts[0].x},${H} Z`;
  // Çizim iki uçta yavaşlayan easing ile; açılma genişliği tam piksel.
  const progress = s.variant > 0 ? 1 : interpolate(frame, [4, 34], [0, 1], {...clamp, easing: EASE_IN_OUT});
  const revealW = px(W * progress) + 10;
  const end = pts[pts.length - 1];
  const endShown = progress >= 0.98;
  const badgeIn = s.variant > 0 ? 1 : enterProgress(frame, 34, 10);
  const ring = 0.25 + (Math.sin(frame / 4) + 1) * 0.15;
  const arrow = s.direction === 'down' ? '▼' : '▲';
  const bodyTop = s.chips.length ? LAYOUT.contentTopWithChips : LAYOUT.contentTop;
  const chartTop = bodyTop + sz(LAYOUT, 150);
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <div
        style={{
          position: 'absolute',
          top: bodyTop + sz(LAYOUT, 20),
          left: LAYOUT.sidePadding,
          right: LAYOUT.sidePadding,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 24,
        }}
      >
        {s.label ? <span style={{fontSize: sz(LAYOUT, 70), color, fontFamily: HEADING, fontWeight: 900}}>{arrow}</span> : null}
        {s.label ? (
          <span lang="tr" style={{fontFamily: HEADING, fontWeight: 800, fontSize: fitFont(s.label, CONTENT_W - 120, sz(LAYOUT, 62), 0.6), color: palette.text}}>
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
            <rect x={0} y={-50} width={revealW} height={H + 100} />
          </clipPath>
        </defs>
        {[0.25, 0.5, 0.75].map((g) => (
          <line key={g} x1={0} x2={W} y1={px(H * g)} y2={px(H * g)} stroke={palette.text} strokeOpacity={0.08} strokeWidth={3} />
        ))}
        <path d={area} fill="url(#area)" clipPath="url(#reveal)" />
        <path d={path} fill="none" stroke={color} strokeWidth={14} strokeLinecap="round" strokeLinejoin="round" clipPath="url(#reveal)" />
        {pts.map((p, i) => {
          const last = i === pts.length - 1;
          const visible = progress >= i / (pts.length - 1) - 0.01;
          if (!visible) return null;
          return (
            <g key={i}>
              {/* Son noktanın nabzı: sabit yarıçaplı halkanın parlaklığı değişir. */}
              {last ? <circle cx={p.x} cy={p.y} r={34} fill={color} opacity={ring} /> : null}
              <circle cx={p.x} cy={p.y} r={last ? 20 : 11} fill={last ? color : palette.text} />
            </g>
          );
        })}
        {s.pointLabels.map((l, i) => (
          <text
            key={i}
            x={pts[i].x}
            y={H + sz(LAYOUT, 58)}
            fill={palette.muted}
            fontFamily={BODY}
            fontWeight={700}
            fontSize={sz(LAYOUT, 36)}
            textAnchor="middle"
            opacity={progress >= i / (pts.length - 1) - 0.01 ? 1 : 0}
          >
            {l}
          </text>
        ))}
      </svg>
      {s.endValue && endShown ? (
        <div
          lang="tr"
          style={{
            position: 'absolute',
            top: Math.max(chartTop + end.y - sz(LAYOUT, 150), bodyTop + sz(LAYOUT, 110)),
            right: LAYOUT.sidePadding - 10,
            background: color,
            color: '#FFFFFF',
            fontFamily: HEADING,
            fontWeight: 900,
            fontSize: fitFont(s.endValue, sz(LAYOUT, 560), sz(LAYOUT, s.variant > 0 ? 76 : 64), 0.66),
            padding: '14px 30px',
            borderRadius: 26,
            boxShadow: '0 20px 50px rgba(0,0,0,0.4)',
            opacity: badgeIn,
            transform: `translateX(${px((1 - badgeIn) * 40)}px)`,
            ...MOVING,
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
  const L = useLayout();
  const words = s.text.split(/\s+/).length;
  const size = words <= 4 ? 110 : words <= 7 ? 92 : 80;
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <Body hasChips={s.chips.length > 0} gap={30}>
        <div style={{fontFamily: HEADING, fontWeight: 900, fontSize: sz(L, 200), lineHeight: 0.6, color: palette.accent, opacity: 0.9, height: sz(L, 90)}}>“</div>
        <StaggerText text={s.text} size={size} highlight={s.highlight} delay={s.variant > 0 ? -30 : 0} />
      </Body>
      <Label text={s.label} top={L.labelTopLow} />
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- photo (uzun video)
// Lisanslı arşiv fotoğrafı. Yavaş zoom YALNIZCA fotoğraf katmanında (üzerinde yazı yok);
// etiket ve çipler sabit kalır (titreme kuralı). Lisans bilgisi video açıklamasındadır.
const Photo: React.FC<{s: PhotoScene}> = ({s}) => {
  const frame = useCurrentFrame();
  const L = useLayout();
  const top = s.chips.length ? L.contentTopWithChips : L.contentTop;
  const zoom = interpolate(frame, [0, s.durationInFrames], [1, 1.08], clamp);
  const pan = interpolate(frame, [0, s.durationInFrames], [0, -1.5], clamp);
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <div
        style={{
          position: 'absolute',
          top,
          bottom: L.height - (s.label ? L.labelTop - sz(L, 24) : L.contentBottom),
          left: L.sidePadding,
          right: L.sidePadding,
          borderRadius: sz(L, 36),
          overflow: 'hidden',
          boxShadow: '0 30px 80px rgba(0,0,0,0.45)',
        }}
      >
        {s.photo ? (
          <Img
            src={staticFile(s.photo.src)}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              objectPosition: s.photo.focus || '50% 30%',
              transform: `scale(${zoom.toFixed(4)}) translateX(${pan.toFixed(3)}%)`,
              ...MOVING,
            }}
          />
        ) : null}
        <div style={{position: 'absolute', inset: 0, background: 'linear-gradient(180deg, rgba(0,0,0,0) 60%, rgba(0,0,0,0.35) 100%)'}} />
      </div>
      <Label text={s.label} top={L.labelTop} />
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- chapter (uzun video)
// Bölüm başlığı kartı: başlık, seslendirmede okunan bölüm başlığıdır (kural 1).
const Chapter: React.FC<{s: ChapterScene}> = ({s}) => {
  const frame = useCurrentFrame();
  const {palette} = useTheme();
  const L = useLayout();
  const line = px(interpolate(frame, [0, 20], [0, sz(L, 420)], {...clamp, easing: EASE_IN_OUT}));
  return (
    <SceneFrame durationInFrames={s.durationInFrames} variant={s.variant} chips={s.chips}>
      <Body hasChips={s.chips.length > 0} gap={50}>
        <div style={{height: sz(L, 12), width: line, background: palette.accent, borderRadius: sz(L, 12)}} />
        <StaggerText text={s.title} size={120} weight={900} delay={4} />
        <div style={{height: sz(L, 12), width: line, background: palette.accent, borderRadius: sz(L, 12)}} />
      </Body>
    </SceneFrame>
  );
};

// ---------------------------------------------------------------- vurgu öğeleri
// 4 sn'den uzun sahnelerde her 3-4 sn'de bir ekrana giren kısa vurgu (o anda söylenen bir
// kelime/rakam): ekran hiçbir zaman 4 sn'den uzun tamamen sabit kalmaz. Sağ üst köşede,
// içerikle çakışmadan birikir; ölçeklenmez, yalnızca opacity + translate.
const Accents: React.FC<{accents: Accent[]}> = ({accents}) => {
  const frame = useCurrentFrame();
  const {palette} = useTheme();
  const L = useLayout();
  const shown = accents.filter((a) => frame >= a.at);
  if (!shown.length) return null;
  return (
    <div
      style={{
        position: 'absolute',
        top: L.contentTop + sz(L, 10),
        right: L.sidePadding,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: sz(L, 16),
      }}
    >
      {shown.map((a, i) => {
        const s = enterProgress(frame, a.at, 10);
        return (
          <div
            key={i}
            lang="tr"
            style={{
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: sz(L, 46),
              textTransform: 'uppercase',
              color: palette.card_text,
              background: palette.accent,
              padding: `${sz(L, 10)}px ${sz(L, 26)}px`,
              borderRadius: sz(L, 16),
              opacity: s,
              transform: `translateX(${px((1 - s) * sz(L, 60))}px)`,
              ...MOVING,
            }}
          >
            {a.text}
          </div>
        );
      })}
    </div>
  );
};

export const SceneView: React.FC<{scene: SceneProps}> = ({scene}) => (
  <>
    <SceneBody scene={scene} />
    {scene.accents && scene.accents.length ? <Accents accents={scene.accents} /> : null}
  </>
);

const SceneBody: React.FC<{scene: SceneProps}> = ({scene}) => {
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
    case 'photo':
      return <Photo s={scene} />;
    case 'chapter':
      return <Chapter s={scene} />;
    default:
      return <AbsoluteFill />;
  }
};
