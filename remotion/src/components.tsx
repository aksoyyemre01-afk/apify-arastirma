import React from 'react';
import {AbsoluteFill, Easing, Img, interpolate, random, staticFile, useCurrentFrame} from 'remotion';
import {BODY, HEADING, formatNumber, parseNumber, sz, useLayout, useTheme} from './theme';
import {LogoRef} from './types';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// ---------------------------------------------------------------- titreme önleme
// Metin/logo/grafik katmanlarında scale/rotate YOK: her karede yeniden ölçeklenen yazı ve
// ince çizgiler kenarlarda titrer (shimmer). Hareket yalnızca opacity ve tam piksele
// yuvarlanmış translate ile yapılır; zoom sadece yumuşak arka plan gradyanına uygulanır.
export const px = (v: number) => Math.round(v);
export const MOVING: React.CSSProperties = {willChange: 'transform, opacity'};
// Yumuşak easing'ler: girişler/sayaçlar hızlı başlayıp yumuşak oturur; çizimler iki uçta yavaşlar.
export const EASE_OUT = Easing.bezier(0.22, 1, 0.36, 1);
export const EASE_IN_OUT = Easing.bezier(0.65, 0, 0.35, 1);

// Kareye bağlı yumuşak giriş (0 -> 1): taşmasız (overshoot yok), deterministik.
export const enterProgress = (frame: number, delay = 0, duration = 14) =>
  interpolate(frame - delay, [0, duration], [0, 1], {...clamp, easing: EASE_OUT});

// ---------------------------------------------------------------- arka plan
// Sürekli hareket eden (kural 5) sade seri zemini: kayan ve yavaşça zoom yapan gradyan,
// tam piksel adımlarla kayan ızgara ve parçacıklar. Tüm rastgele değerler Remotion'un
// random(seed) fonksiyonundan gelir: her render'da ve her karede aynıdır.
// Sahne tonu: seri paletinden bir renk, 0-1 arası güç. Zemin yapısı hep aynı kalır,
// yalnızca üzerine hafif bir renk yıkaması gelir.
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

// Parçacıklar yerleşimin boyutuna göre dağılır (dikeyde 1080x1920 - eski değerlerle aynı).
const particles = (w: number, h: number) =>
  new Array(18).fill(0).map((_, i) => ({
    x: Math.round(random(`px${i}`) * w),
    y0: random(`py${i}`) * h,
    speed: 0.4 + random(`ps${i}`) * 1.2,
    size: Math.round(4 + random(`pz${i}`) * 8),
    opacity: 0.12 + random(`po${i}`) * 0.2,
  }));

export const Background: React.FC<{tint?: Tint | null; prevTint?: Tint | null}> = ({tint, prevTint}) => {
  const frame = useCurrentFrame();
  const {palette} = useTheme();
  const L = useLayout();
  const PARTICLES = particles(L.width, L.height);
  const gx = 50 + Math.sin(frame / 90) * 25;
  const gy = 35 + Math.cos(frame / 110) * 15;
  // Tek zoom katmanı: yalnızca yumuşak gradyan ve ton (ince çizgi/metin yok, titremez).
  const zoom = 1.04 + Math.sin(frame / 120) * 0.04;
  const gridShift = px((frame * 0.6) % 90);
  return (
    <AbsoluteFill style={{backgroundColor: palette.background, overflow: 'hidden'}}>
      <AbsoluteFill style={{transform: `scale(${zoom.toFixed(4)})`, ...MOVING}}>
        <AbsoluteFill
          style={{
            background: `radial-gradient(circle at ${gx.toFixed(2)}% ${gy.toFixed(2)}%, ${palette.background_alt} 0%, ${palette.background} 62%)`,
          }}
        />
        {prevTint ? <TintLayer tint={prevTint} /> : null}
        {tint ? <TintLayer tint={tint} /> : null}
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          backgroundImage: `linear-gradient(${palette.text}0D 2px, transparent 2px), linear-gradient(90deg, ${palette.text}0D 2px, transparent 2px)`,
          backgroundSize: '90px 90px',
          backgroundPosition: `0px ${gridShift}px`,
          maskImage: 'radial-gradient(circle at 50% 40%, black 20%, transparent 75%)',
        }}
      />
      {PARTICLES.map((p, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            left: p.x,
            top: 0,
            width: p.size,
            height: p.size,
            borderRadius: p.size,
            background: palette.accent,
            opacity: p.opacity,
            transform: `translateY(${px((p.y0 - frame * p.speed + L.height * 4) % L.height)}px)`,
            ...MOVING,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- sahne kamerası
// Her sahne: yumuşak giriş (opacity + yukarı kayma), kısa çıkış. variant>0 bir "kamera
// kesmesi"dir: içerik büyütülmez; yandan kısa bir kayma + beyaz flaş ile ekran değişir.
// Sürekli hareket hissini arka plan (gradyan zoom, ızgara, parçacıklar) verir.
export const SceneFrame: React.FC<{
  durationInFrames: number;
  variant: number;
  // Logo çipleri kendi sabit bölgesinde çizilir.
  chips?: LogoRef[];
  children: React.ReactNode;
}> = ({durationInFrames, variant, chips = [], children}) => {
  const frame = useCurrentFrame();
  const LAYOUT = useLayout();
  const enter = enterProgress(frame, 0, 12);
  const exit = interpolate(frame, [durationInFrames - 4, durationInFrames], [1, 0], clamp);
  const opacity = Math.min(variant === 0 ? interpolate(frame, [0, 6], [0, 1], clamp) : 1, exit);
  const dx = variant === 0 ? 0 : px((1 - enter) * (variant % 2 ? 60 : -60));
  const dy = variant === 0 ? px((1 - enter) * 50) : 0;
  const clipTop = chips.length ? LAYOUT.sceneClipTopWithChips : LAYOUT.sceneClipTop;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{clipPath: `inset(${clipTop}px 0 0 0)`}}>
        <AbsoluteFill style={{transform: `translate(${dx}px, ${dy}px)`, opacity, ...MOVING}}>{children}</AbsoluteFill>
      </AbsoluteFill>
      {chips.length ? (
        <AbsoluteFill style={{opacity}}>
          <Chips chips={chips} />
        </AbsoluteFill>
      ) : null}
      {variant > 0 ? (
        <AbsoluteFill style={{background: 'white', opacity: interpolate(frame, [0, 4], [0.3, 0], clamp), pointerEvents: 'none'}} />
      ) : null}
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- logo kartı
// Logolar her zaman düz, açık renkli kart üzerinde ve tamamı görünecek şekilde
// (object-fit: contain + iç boşluk). Logo dosyası yoksa marka adı yazı logosu olur.
// Gizli (gizem) marka soru işaretli kutudur; revealAt karesinde logoya geçer (çapraz
// geçiş + halka). Kart hiçbir zaman ölçeklenmez ya da döndürülmez.
export const LogoCard: React.FC<{
  logo: LogoRef;
  width: number;
  height: number;
  delay?: number;
  dim?: boolean;
  highlight?: boolean;
}> = ({logo, width, height, delay = 0, dim, highlight}) => {
  const frame = useCurrentFrame();
  const {palette} = useTheme();
  const w = px(width);
  const h = px(height);
  const appear = enterProgress(frame, delay, 12);
  const revealAt = logo.revealAt;
  const since = revealAt !== null ? frame - revealAt : 999;
  // Reveal: "?" kutusu 6 karede söner, logo aynı yerde belirir.
  const reveal = !logo.hidden ? 1 : revealAt === null ? 0 : interpolate(since, [0, 6], [0, 1], {...clamp, easing: EASE_OUT});
  const radius = px(Math.min(w, h) * 0.14);
  const pad = px(Math.min(w, h) * 0.13);
  const fontSize = px(Math.min(h * 0.42, (w * 1.55) / Math.max(logo.name.length, 3)));
  const face: React.CSSProperties = {
    position: 'absolute',
    inset: 0,
    borderRadius: radius,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxSizing: 'border-box',
    boxShadow: '0 30px 80px rgba(0,0,0,0.45)',
  };

  return (
    <div
      style={{
        width: w,
        height: h,
        position: 'relative',
        flexShrink: 0,
        opacity: appear * (dim ? 0.45 : 1),
        transform: `translateY(${px((1 - appear) * 30)}px)`,
        ...MOVING,
      }}
    >
      {reveal > 0 ? (
        <div
          style={{
            ...face,
            background: palette.card,
            padding: pad,
            opacity: reveal,
            boxShadow: `0 30px 80px rgba(0,0,0,0.45)${highlight ? `, 0 0 0 8px ${palette.accent}` : ''}`,
          }}
        >
          {logo.src ? (
            <Img src={staticFile(logo.src)} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
          ) : (
            <span style={{fontFamily: HEADING, fontWeight: 900, fontSize, color: palette.card_text, textAlign: 'center', lineHeight: 1.05}}>
              {logo.name}
            </span>
          )}
        </div>
      ) : null}
      {reveal < 1 ? (
        <div style={{...face, background: palette.background_alt, border: `8px dashed ${palette.accent}`, opacity: 1 - reveal}}>
          {/* Bekleme nabzı ölçekle değil parlaklıkla verilir. */}
          <span
            style={{
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: px(h * 0.62),
              color: palette.accent,
              lineHeight: 1,
              opacity: 0.75 + Math.sin(frame / 5) * 0.25,
            }}
          >
            ?
          </span>
        </div>
      ) : null}
      {revealAt !== null && logo.hidden && since >= 0 && since < 24 ? (
        <div
          style={{
            position: 'absolute',
            inset: -20 - px(since * 6),
            borderRadius: radius + 20 + px(since * 6),
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
// bölgesiyle asla çakışmaz.
export const Chips: React.FC<{chips: LogoRef[]}> = ({chips}) => {
  const LAYOUT = useLayout();
  if (!chips.length) return null;
  const h = px(LAYOUT.chipsHeight * 0.9);
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
        gap: sz(LAYOUT, 40),
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
  const {palette} = useTheme();
  const LAYOUT = useLayout();
  if (!text) return null;
  const s = enterProgress(frame, delay, 12);
  size = sz(LAYOUT, size);
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
          padding: `${px(size * 0.3)}px ${px(size * 0.6)}px`,
          borderRadius: size,
          textAlign: 'center',
          opacity: s,
          transform: `translateY(${px((1 - s) * 30)}px)`,
          ...MOVING,
        }}
      >
        {text}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- sayaç
// "125" -> 0'dan 125'e yumuşak easing ile sayar (Türkçe biçim). Sayı değilse sadece belirir.
// Kullanan yerler tabular-nums kullanır: rakam genişliği sabit kalır, metin yana titremez.
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
  const t = interpolate(frame - start, [0, durationInFrames], [0, 1], {...clamp, easing: EASE_OUT});
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
  px(Math.min(maxSize, maxWidth / Math.max(text.length * charRatio, 1)));
