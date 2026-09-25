import React from 'react';
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  random,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {BODY, HEADING, LAYOUT, formatNumber, parseNumber, useTheme} from './theme';
import {LogoRef} from './types';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// ---------------------------------------------------------------- arka plan
// Sürekli hareket eden (kural 5) sade seri zemini: kayan gradyan + ızgara + parçacıklar.
// Sahne tonu: seri paletinden bir renk, 0-1 arası güç. Zemin yapısı (gradyan, ızgara,
// parçacıklar) hep aynı kalır, yalnızca üzerine hafif bir renk yıkaması gelir.
export type Tint = {color: string; strength: number};

const alphaHex = (a: number) =>
  Math.round(Math.max(0, Math.min(1, a)) * 255)
    .toString(16)
    .padStart(2, '0');

const TintLayer: React.FC<{tint: Tint}> = ({tint}) => (
  <>
    <AbsoluteFill
      style={{background: `radial-gradient(circle at 50% 42%, ${tint.color}${alphaHex(0.3 * tint.strength)} 0%, transparent 65%)`}}
    />
    <AbsoluteFill style={{background: `${tint.color}${alphaHex(0.08 * tint.strength)}`}} />
  </>
);

export const Background: React.FC<{tint?: Tint | null; prevTint?: Tint | null}> = ({tint, prevTint}) => {
  const frame = useCurrentFrame();
  const {palette} = useTheme();
  const gx = 50 + Math.sin(frame / 90) * 25;
  const gy = 35 + Math.cos(frame / 110) * 15;
  const gridShift = (frame * 0.6) % 90;
  return (
    <AbsoluteFill style={{backgroundColor: palette.background, overflow: 'hidden'}}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at ${gx}% ${gy}%, ${palette.background_alt} 0%, ${palette.background} 62%)`,
        }}
      />
      {prevTint ? <TintLayer tint={prevTint} /> : null}
      {tint ? <TintLayer tint={tint} /> : null}
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${palette.text}0D 2px, transparent 2px), linear-gradient(90deg, ${palette.text}0D 2px, transparent 2px)`,
          backgroundSize: '90px 90px',
          backgroundPosition: `0px ${gridShift}px`,
          maskImage: 'radial-gradient(circle at 50% 40%, black 20%, transparent 75%)',
        }}
      />
      {new Array(18).fill(0).map((_, i) => {
        const x = random(`px${i}`) * 1080;
        const speed = 0.4 + random(`ps${i}`) * 1.2;
        const y = (random(`py${i}`) * 1920 - frame * speed + 1920 * 2) % 1920;
        const size = 4 + random(`pz${i}`) * 8;
        return (
          <div
            key={i}
            style={{
              position: 'absolute',
              left: x,
              top: y,
              width: size,
              height: size,
              borderRadius: size,
              background: palette.accent,
              opacity: 0.12 + random(`po${i}`) * 0.2,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- sahne kamerası
// Her sahne: animasyonlu giriş, sürekli yavaş zoom, kısa çıkış. variant>0 bir
// "kamera kesmesi"dir (aynı içerik, yakın plan) - ekran en geç ~3 sn'de değişir.
export const SceneFrame: React.FC<{
  durationInFrames: number;
  variant: number;
  focus?: {x: number; y: number};
  // Logo çipleri kendi sabit bölgesinde, kamera zoom'undan bağımsız çizilir.
  chips?: LogoRef[];
  children: React.ReactNode;
}> = ({durationInFrames, variant, focus, chips = [], children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 14, mass: 0.7}});
  const drift = interpolate(frame, [0, durationInFrames], [0, 0.05], clamp);
  const exit = interpolate(frame, [durationInFrames - 4, durationInFrames], [1, 0], clamp);
  let scale: number;
  let translateY: number;
  let opacity: number;
  if (variant === 0) {
    scale = interpolate(enter, [0, 1], [0.86, 1]) + drift;
    translateY = interpolate(enter, [0, 1], [70, 0]);
    opacity = Math.min(interpolate(frame, [0, 6], [0, 1], clamp), exit);
  } else {
    const punch = spring({frame, fps, config: {damping: 18}});
    scale = interpolate(punch, [0, 1], [1.16, 1.08 + 0.03 * Math.min(variant, 2)]) + drift;
    translateY = 0;
    opacity = exit;
  }
  const origin = focus ? `${focus.x}px ${focus.y}px` : '50% 38%';
  const clipTop = chips.length ? LAYOUT.sceneClipTopWithChips : LAYOUT.sceneClipTop;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{clipPath: `inset(${clipTop}px 0 0 0)`}}>
        <AbsoluteFill style={{transform: `translateY(${translateY}px) scale(${scale})`, transformOrigin: origin, opacity}}>
          {children}
        </AbsoluteFill>
      </AbsoluteFill>
      {chips.length ? (
        <AbsoluteFill style={{opacity}}>
          <Chips chips={chips} />
        </AbsoluteFill>
      ) : null}
      {variant > 0 ? (
        <AbsoluteFill
          style={{background: 'white', opacity: interpolate(frame, [0, 4], [0.35, 0], clamp), pointerEvents: 'none'}}
        />
      ) : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- logo kartı
// Logolar her zaman düz, açık renkli kart üzerinde ve tamamı görünecek şekilde
// (object-fit: contain + iç boşluk). Logo dosyası yoksa marka adı yazı logosu olur.
// Gizli (gizem) marka soru işaretli kutudur; revealAt karesinde logoya döner.
export const LogoCard: React.FC<{
  logo: LogoRef;
  width: number;
  height: number;
  delay?: number;
  dim?: boolean;
}> = ({logo, width, height, delay = 0, dim}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {palette} = useTheme();
  const appear = spring({frame: frame - delay, fps, config: {damping: 12, mass: 0.6}});
  const revealAt = logo.revealAt;
  const concealed = logo.hidden && (revealAt === null || frame < revealAt);
  const since = revealAt !== null ? frame - revealAt : 999;
  const revealSpring = revealAt !== null ? spring({frame: since, fps, config: {damping: 9, mass: 0.7}}) : 1;
  const flip = revealAt !== null && logo.hidden ? interpolate(revealSpring, [0, 1], [90, 0]) : 0;
  const radius = Math.min(width, height) * 0.14;
  const pad = Math.min(width, height) * 0.13;

  const base: React.CSSProperties = {
    width,
    height,
    borderRadius: radius,
    transform: `scale(${appear * (concealed ? 1 + Math.sin(frame / 5) * 0.02 : 1)}) rotateY(${concealed ? 0 : flip}deg)`,
    opacity: dim ? 0.45 : 1,
    boxShadow: '0 30px 80px rgba(0,0,0,0.45)',
    position: 'relative',
    flexShrink: 0,
  };

  if (concealed) {
    return (
      <div
        style={{
          ...base,
          background: `${palette.background_alt}`,
          border: `8px dashed ${palette.accent}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <span style={{fontFamily: HEADING, fontWeight: 900, fontSize: height * 0.62, color: palette.accent, lineHeight: 1}}>
          ?
        </span>
      </div>
    );
  }

  const fontSize = Math.min(height * 0.42, (width * 1.55) / Math.max(logo.name.length, 3));
  return (
    <div style={{...base, background: palette.card, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: pad, boxSizing: 'border-box'}}>
      {logo.src ? (
        <Img src={staticFile(logo.src)} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
      ) : (
        <span style={{fontFamily: HEADING, fontWeight: 900, fontSize, color: palette.card_text, textAlign: 'center', lineHeight: 1.05}}>
          {logo.name}
        </span>
      )}
      {revealAt !== null && logo.hidden && since >= 0 && since < 24 ? (
        <div
          style={{
            position: 'absolute',
            inset: -20 - since * 6,
            borderRadius: radius + 20 + since * 6,
            border: `10px solid ${palette.accent}`,
            opacity: interpolate(since, [0, 24], [1, 0]),
          }}
        />
      ) : null}
    </div>
  );
};

// ---------------------------------------------------------------- küçük logo çipleri
// Sabit çip bölgesinde (LAYOUT.chipsTop..+chipsHeight) dikeyde ortalanır; rozet
// bölgesiyle asla çakışmaz. Giriş zıplaması taşmasın diye kart bölgeden %10 küçük.
export const Chips: React.FC<{chips: LogoRef[]}> = ({chips}) => {
  if (!chips.length) return null;
  const h = Math.round(LAYOUT.chipsHeight * 0.9);
  return (
    <div
      style={{
        position: 'absolute',
        top: LAYOUT.chipsTop,
        height: LAYOUT.chipsHeight,
        left: 0,
        right: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 40,
      }}
    >
      {chips.map((c, i) => (
        <LogoCard key={i} logo={c} width={h * 1.9} height={h} delay={2 + i * 3} />
      ))}
    </div>
  );
};

// ---------------------------------------------------------------- etiket
export const Label: React.FC<{text: string; delay?: number; size?: number; top: number}> = ({text, delay = 8, size = 58, top}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {palette} = useTheme();
  if (!text) return null;
  const s = spring({frame: frame - delay, fps, config: {damping: 14}});
  return (
    <div style={{position: 'absolute', top, left: LAYOUT.sidePadding, right: LAYOUT.sidePadding, display: 'flex', justifyContent: 'center'}}>
      <div
        lang="tr"
        style={{
          fontFamily: BODY,
          fontWeight: 700,
          fontSize: size,
          color: palette.text,
          background: `${palette.text}14`,
          border: `3px solid ${palette.text}26`,
          padding: `${size * 0.3}px ${size * 0.6}px`,
          borderRadius: size,
          textAlign: 'center',
          opacity: s,
          transform: `translateY(${(1 - s) * 30}px)`,
        }}
      >
        {text}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- sayaç
// "125" -> 0'dan 125'e sayar (Türkçe biçim). Sayı değilse sadece belirir.
export const Counter: React.FC<{value: string; durationInFrames?: number; start?: number; animate?: boolean}> = ({
  value,
  durationInFrames = 26,
  start = 0,
  animate = true,
}) => {
  const frame = useCurrentFrame();
  const parsed = parseNumber(value);
  if (!parsed || !animate) return <>{value}</>;
  // Yıl/dönem ("1998", "1990'LAR"): binlik ayırıcı yok, geçmişten sayar.
  const isYear = !parsed.prefix && Number.isInteger(parsed.num) && parsed.num >= 1800 && parsed.num <= 2100 && !/[.,]/.test(value);
  const from = isYear ? parsed.num - 25 : 0;
  const t = interpolate(frame - start, [0, durationInFrames], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
  const current = from + (parsed.num - from) * t;
  const shown = isYear ? String(Math.round(current)) : formatNumber(current, parsed.decimals);
  return (
    <>
      {parsed.prefix}
      {shown}
      {parsed.suffix}
    </>
  );
};

export const fitFont = (text: string, maxWidth: number, maxSize: number, charRatio = 0.62) =>
  Math.min(maxSize, maxWidth / Math.max(text.length * charRatio, 1));
