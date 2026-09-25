import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Background, Tint} from './components';
import {SceneView} from './scenes';
import {BODY, HEADING, LAYOUT, ThemeProvider, useTheme} from './theme';
import {CaptionPage, LogoRef, Outro as OutroProps, SceneProps, ShortProps} from './types';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const FIRST_FRAME_LEAD = 10;

// Sahne `lead` kare erken başlatıldığında süreyi ve reveal karelerini aynı miktarda kaydırır.
const shiftScene = (s: SceneProps, lead: number): SceneProps => {
  const shift = (r: LogoRef | null): LogoRef | null =>
    r && r.revealAt !== null ? {...r, revealAt: r.revealAt + lead} : r;
  const out = {...s, durationInFrames: s.durationInFrames + lead, chips: s.chips.map((c) => shift(c) as LogoRef)};
  if (out.type === 'logo_intro') out.logo = shift(out.logo);
  if (out.type === 'comparison') {
    out.left = shift(out.left);
    out.right = shift(out.right);
  }
  return out;
};

// ---------------------------------------------------------------- altyazı (kural 6)
// Ses ile kelime senkronu: o an söylenen kelime vurgu renginde ve hafifçe yukarıda.
// Vurgu kelimenin genişliğini DEĞİŞTİRMEZ (scale yok); kelimeler arasındaki boşluk
// yazı konturu düşüldükten sonra da her zaman görünür kalır.
const CAPTION_SIZE = 84;
const CAPTION_STROKE = 12;
const CAPTION_WORD_GAP = Math.round(CAPTION_SIZE * 0.34) + CAPTION_STROKE;
const Caption: React.FC<{page: CaptionPage}> = ({page}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {palette} = useTheme();
  const pop = spring({frame, fps, config: {damping: 16, mass: 0.5}});
  return (
    <div
      style={{
        position: 'absolute',
        top: LAYOUT.captionTop,
        height: LAYOUT.captionHeight,
        left: 50,
        right: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        lang="tr"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: `0 ${CAPTION_WORD_GAP}px`,
          transform: `scale(${interpolate(pop, [0, 1], [0.85, 1])})`,
        }}
      >
        {page.words.map((w, i) => {
          const active = frame >= w.start && (frame < (page.words[i + 1]?.start ?? page.durationInFrames));
          return (
            <span
              key={i}
              style={{
                fontFamily: HEADING,
                fontWeight: 900,
                fontSize: CAPTION_SIZE,
                lineHeight: 1.15,
                color: active ? palette.accent : palette.text,
                transform: `translateY(${active ? -6 : 0}px)`,
                display: 'inline-block',
                whiteSpace: 'nowrap',
                WebkitTextStroke: `${CAPTION_STROKE}px ${palette.background}`,
                paintOrder: 'stroke fill',
                textShadow: '0 8px 24px rgba(0,0,0,0.55)',
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- seri rozeti (kural 7)
// Metin config/brand.json'dan gelir; boşsa hiç çizilmez.
const Badge: React.FC<{text: string; intro: boolean}> = ({text, intro}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {palette} = useTheme();
  if (!text) return null;
  const s = intro ? spring({frame, fps, config: {damping: 15}}) : 1;
  const sweep = intro ? interpolate(frame, [0, 16], [0, 120], clamp) : 120;
  return (
    <div
      style={{
        position: 'absolute',
        top: LAYOUT.badgeTop,
        height: LAYOUT.badgeHeight,
        left: 0,
        right: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
      }}
    >
      <div
        lang="tr"
        style={{
          position: 'relative',
          overflow: 'hidden',
          fontFamily: HEADING,
          fontWeight: 800,
          fontSize: 38,
          lineHeight: 1.2,
          letterSpacing: 3,
          textTransform: 'uppercase',
          color: palette.card_text,
          background: palette.accent,
          padding: '10px 30px',
          borderRadius: 16,
          transform: `translateY(${(1 - s) * -120}px)`,
        }}
      >
        {text}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: `linear-gradient(100deg, transparent ${sweep - 30}%, rgba(255,255,255,0.7) ${sweep - 15}%, transparent ${sweep}%)`,
          }}
        />
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- outro (kural 4, 7)
const Outro: React.FC<{o: OutroProps}> = ({o}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const {palette} = useTheme();
  const s = spring({frame, fps, config: {damping: 14}});
  const words = o.cta.split(/\s+/).filter(Boolean);
  const pulse = 1 + Math.sin(frame / 4) * 0.04;
  return (
    <AbsoluteFill style={{background: `${palette.background}F2`, opacity: interpolate(frame, [0, 6], [0, 1], clamp)}}>
      <div
        style={{
          position: 'absolute',
          top: 300,
          bottom: 1920 - 1400,
          left: LAYOUT.sidePadding,
          right: LAYOUT.sidePadding,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 60,
          textAlign: 'center',
        }}
      >
        {o.seriesName ? (
          <div lang="tr" style={{fontFamily: HEADING, fontWeight: 800, fontSize: 44, letterSpacing: 4, textTransform: 'uppercase', color: palette.accent, transform: `scale(${s})`}}>
            {o.seriesName}
          </div>
        ) : null}
        {words.length ? (
          <div lang="tr" style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '10px 22px'}}>
            {words.map((w, i) => {
              const ws = spring({frame: frame - 3 - i * 2, fps, config: {damping: 13}});
              return (
                <span key={i} style={{fontFamily: HEADING, fontWeight: 900, fontSize: 88, lineHeight: 1.1, color: palette.text, opacity: ws, transform: `translateY(${(1 - ws) * 40}px)`, display: 'inline-block'}}>
                  {w}
                </span>
              );
            })}
          </div>
        ) : null}
        {o.partText ? (
          <div lang="tr" style={{fontFamily: BODY, fontWeight: 700, fontSize: 48, color: palette.muted, opacity: interpolate(frame, [10, 18], [0, 1], clamp)}}>
            {o.partText}
          </div>
        ) : null}
        {o.followText ? (
          <div
            lang="tr"
            style={{
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: 56,
              color: palette.card_text,
              background: palette.accent,
              padding: '22px 60px',
              borderRadius: 80,
              transform: `scale(${interpolate(frame, [12, 20], [0, 1], clamp) * pulse})`,
            }}
          >
            {o.followText} →
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- kompozisyon
const Inner: React.FC<ShortProps> = (props) => {
  const frame = useCurrentFrame();
  const {palette} = props.theme;
  const active = props.scenes.find((s) => frame >= s.from && frame < s.from + s.durationInFrames);
  // Kural 5 (görsel çeşitlilik): zemin tonu sahneye göre hafifçe değişir, seri paletinin
  // dışına çıkmaz. Ton geçişi ~10 karede yumuşak yapılır.
  const toneTint = (s: SceneProps | undefined): Tint | null => {
    if (!s) return null;
    if (s.tone === 'rise') return {color: palette.up, strength: 1};
    if (s.tone === 'fall') return {color: palette.down, strength: 1};
    if (s.type === 'logo_intro' || s.type === 'big_number') return {color: palette.accent, strength: 0.45};
    if (s.type === 'timeline' || s.type === 'comparison') return {color: palette.muted, strength: 0.5};
    return null;
  };
  const activeIdx = active ? props.scenes.indexOf(active) : -1;
  const cur = toneTint(active);
  const prev = activeIdx > 0 ? toneTint(props.scenes[activeIdx - 1]) : null;
  const fade = active ? interpolate(frame - active.from, [0, 10], [0, 1], clamp) : 1;
  const same = cur?.color === prev?.color && cur?.strength === prev?.strength;
  const tint = cur && !same ? {...cur, strength: cur.strength * fade} : cur;
  const prevTint = prev && !same ? {...prev, strength: prev.strength * (1 - fade)} : null;
  const outroFrom = props.outro?.from ?? props.durationInFrames;
  const musicFadeFrom = props.durationInFrames - 30;
  return (
    <AbsoluteFill>
      <Background tint={tint} prevTint={prevTint} />
      {props.scenes.map((s, i) => {
        // İlk sahne giriş animasyonunun ortasından başlar: videonun ilk karesi (otomatik
        // oynatma/kapak) asla boş olmaz (kural 4).
        const lead = s.from === 0 ? FIRST_FRAME_LEAD : 0;
        return (
          <Sequence key={i} from={s.from - lead} durationInFrames={s.durationInFrames + lead} layout="none">
            <SceneView scene={lead ? shiftScene(s, lead) : s} />
          </Sequence>
        );
      })}
      <Sequence from={-FIRST_FRAME_LEAD} durationInFrames={outroFrom + FIRST_FRAME_LEAD} layout="none">
        <Badge text={props.theme.badgeText} intro={props.theme.intro} />
      </Sequence>
      {props.captions.map((c, i) => (
        <Sequence key={`c${i}`} from={c.from} durationInFrames={c.durationInFrames} layout="none">
          <Caption page={c} />
        </Sequence>
      ))}
      {props.outro ? (
        <Sequence from={props.outro.from} durationInFrames={props.outro.durationInFrames}>
          <Outro o={props.outro} />
        </Sequence>
      ) : null}
      {props.audio.narration ? <Audio src={staticFile(props.audio.narration)} /> : null}
      {props.audio.music ? (
        <Audio
          src={staticFile(props.audio.music)}
          loop
          volume={(f) => props.audio.musicVolume * interpolate(f, [0, 10, musicFadeFrom, props.durationInFrames], [0, 1, 1, 0], clamp)}
        />
      ) : null}
      {props.audio.sfx.map((x, i) => (
        <Sequence key={`s${i}`} from={x.from} layout="none">
          <Audio src={staticFile(x.src)} volume={props.audio.sfxVolume} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const Short: React.FC<ShortProps> = (props) => (
  <ThemeProvider theme={props.theme}>
    <Inner {...props} />
  </ThemeProvider>
);
