import React from 'react';
import {AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Background, EASE_IN_OUT, MOVING, Tint, enterProgress, px} from './components';
import {SceneView} from './scenes';
import {BODY, HEADING, LAYOUT, LAYOUT_LANDSCAPE, Layout, LayoutProvider, ThemeProvider, sz, useLayout, useTheme} from './theme';
import {CaptionPage, LogoRef, Outro as OutroProps, SceneProps, ShortProps} from './types';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const FIRST_FRAME_LEAD = 10;

// Sahne `lead` kare erken başlatıldığında süreyi ve reveal karelerini aynı miktarda kaydırır.
const shiftScene = (s: SceneProps, lead: number): SceneProps => {
  const shift = (r: LogoRef | null): LogoRef | null =>
    r && r.revealAt !== null ? {...r, revealAt: r.revealAt + lead} : r;
  const out = {...s, durationInFrames: s.durationInFrames + lead, chips: s.chips.map((c) => shift(c) as LogoRef)};
  if (out.accents) out.accents = out.accents.map((a) => ({...a, at: a.at + lead}));
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
  const {palette} = useTheme();
  const LAYOUT = useLayout();
  const size = sz(LAYOUT, CAPTION_SIZE);
  const stroke = sz(LAYOUT, CAPTION_STROKE);
  // Sayfa girişi ölçeksiz: kısa opacity + 20 px yukarı kayma (yazı titremez).
  const pop = enterProgress(frame, 0, 6);
  return (
    <div
      style={{
        position: 'absolute',
        top: LAYOUT.captionTop,
        height: LAYOUT.captionHeight,
        left: LAYOUT.captionSide,
        right: LAYOUT.captionSide,
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
          gap: `0 ${LAYOUT.scale === 1 ? CAPTION_WORD_GAP : Math.round(size * 0.34) + stroke}px`,
          opacity: pop,
          transform: `translateY(${px((1 - pop) * 20)}px)`,
          ...MOVING,
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
                fontSize: size,
                lineHeight: 1.15,
                color: active ? palette.accent : palette.text,
                transform: `translateY(${active ? -sz(LAYOUT, 6) : 0}px)`,
                display: 'inline-block',
                whiteSpace: 'nowrap',
                WebkitTextStroke: `${stroke}px ${palette.background}`,
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
  const {palette} = useTheme();
  const LAYOUT = useLayout();
  if (!text) return null;
  const s = intro ? enterProgress(frame, 0, 14) : 1;
  const sweep = intro ? px(interpolate(frame, [0, 16], [0, 120], {...clamp, easing: EASE_IN_OUT})) : 120;
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
          fontSize: sz(LAYOUT, 38),
          lineHeight: 1.2,
          letterSpacing: 3,
          textTransform: 'uppercase',
          color: palette.card_text,
          background: palette.accent,
          padding: `${sz(LAYOUT, 10)}px ${sz(LAYOUT, 30)}px`,
          borderRadius: sz(LAYOUT, 16),
          transform: `translateY(${px((1 - s) * -120)}px)`,
          ...MOVING,
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
  const {palette} = useTheme();
  const LAYOUT = useLayout();
  const s = enterProgress(frame, 0, 12);
  const words = o.cta.split(/\s+/).filter(Boolean);
  const button = enterProgress(frame, 12, 10);
  // Takip butonu tek satırdır: uzun metinde (ör. kanal adı içeren) yazı küçülür, satır kırılmaz.
  const followSize = Math.min(56, Math.floor(1300 / ((o.followText || '').length + 2)));
  return (
    <AbsoluteFill style={{background: `${palette.background}F2`, opacity: interpolate(frame, [0, 6], [0, 1], clamp)}}>
      <div
        style={{
          position: 'absolute',
          top: LAYOUT.outroTop,
          bottom: LAYOUT.height - LAYOUT.outroBottom,
          left: LAYOUT.sidePadding,
          right: LAYOUT.sidePadding,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: sz(LAYOUT, 60),
          textAlign: 'center',
        }}
      >
        {o.seriesName ? (
          <div lang="tr" style={{fontFamily: HEADING, fontWeight: 800, fontSize: sz(LAYOUT, 44), letterSpacing: 4, textTransform: 'uppercase', color: palette.accent, opacity: s, transform: `translateY(${px((1 - s) * 30)}px)`, ...MOVING}}>
            {o.seriesName}
          </div>
        ) : null}
        {words.length ? (
          <div lang="tr" style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '10px 22px'}}>
            {words.map((w, i) => {
              const ws = enterProgress(frame, 3 + i * 2, 12);
              return (
                <span key={i} style={{fontFamily: HEADING, fontWeight: 900, fontSize: sz(LAYOUT, 88), lineHeight: 1.1, color: palette.text, opacity: ws, transform: `translateY(${px((1 - ws) * 40)}px)`, display: 'inline-block', ...MOVING}}>
                  {w}
                </span>
              );
            })}
          </div>
        ) : null}
        {o.partText ? (
          <div lang="tr" style={{fontFamily: BODY, fontWeight: 700, fontSize: sz(LAYOUT, 48), color: palette.muted, opacity: interpolate(frame, [10, 18], [0, 1], clamp)}}>
            {o.partText}
          </div>
        ) : null}
        {o.followText ? (
          <div
            lang="tr"
            style={{
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: sz(LAYOUT, followSize),
              whiteSpace: 'nowrap',
              color: palette.card_text,
              background: palette.accent,
              padding: `${sz(LAYOUT, 22)}px ${sz(LAYOUT, 48)}px`,
              borderRadius: sz(LAYOUT, 80),
              opacity: button,
              transform: `translateY(${px((1 - button) * 30)}px)`,
              ...MOVING,
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
          <Audio src={staticFile(x.src)} volume={Math.min((x.volume ?? 1) * props.audio.sfxVolume, 1)} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

const withLayout = (layout: Layout): React.FC<ShortProps> => (props) => (
  <LayoutProvider layout={layout}>
    <ThemeProvider theme={props.theme}>
      <Inner {...props} />
    </ThemeProvider>
  </LayoutProvider>
);

// Dikey short (1080x1920) ve yatay uzun video (1920x1080) aynı sahne/altyazı/ses yapısını
// kullanır; yalnızca yerleşim (bölgeler ve boyut çarpanı) farklıdır.
export const Short = withLayout(LAYOUT);
export const Long = withLayout(LAYOUT_LANDSCAPE);
