import React from 'react';
import {AbsoluteFill} from 'remotion';
import {Background, LogoCard, fitFont} from './components';
import {HEADING, LAYOUT_LANDSCAPE, LayoutProvider, ThemeProvider, useTheme} from './theme';
import {ThumbnailProps} from './types';

// Uzun video küçük resmi (1280x720, tek kare): solda büyük rakam (ya da en fazla 5 kelimelik
// çarpıcı başlık), sağda marka logosu. Metin doğrulanmış olgulardan gelir (agents/long_video.py).
const Inner: React.FC<ThumbnailProps> = (p) => {
  const {palette} = useTheme();
  const tint = p.tone === 'fall' ? palette.down : p.tone === 'rise' ? palette.up : palette.accent;
  const leftW = p.logo ? 760 : 1160;
  return (
    <AbsoluteFill>
      <Background tint={{color: tint, strength: 1}} />
      <AbsoluteFill style={{background: `linear-gradient(90deg, ${palette.background}E6 0%, ${palette.background}55 70%, transparent 100%)`}} />
      <div
        style={{
          position: 'absolute',
          left: 60,
          top: 60,
          bottom: 60,
          width: leftW,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          gap: 10,
        }}
      >
        {p.value ? (
          <div style={{fontFamily: HEADING, fontWeight: 900, fontSize: fitFont(p.value, leftW, 300, 0.64), lineHeight: 1, color: palette.text, textShadow: `0 0 40px ${tint}AA`}}>
            {p.value}
          </div>
        ) : null}
        {p.unit ? (
          <div lang="tr" style={{fontFamily: HEADING, fontWeight: 900, fontSize: fitFont(p.unit, leftW, 110, 0.7), color: palette.accent, letterSpacing: 2}}>
            {p.unit}
          </div>
        ) : null}
        {p.headline ? (
          <div
            lang="tr"
            style={{
              fontFamily: HEADING,
              fontWeight: 900,
              fontSize: p.value ? 64 : fitFont(p.headline, leftW * 1.9, 120, 0.6),
              lineHeight: 1.05,
              color: p.value ? palette.text : palette.accent,
              textTransform: 'uppercase',
            }}
          >
            {p.headline}
          </div>
        ) : null}
      </div>
      {p.logo ? (
        <div style={{position: 'absolute', right: 60, top: 0, bottom: 0, display: 'flex', alignItems: 'center'}}>
          <LogoCard logo={p.logo} width={400} height={240} />
        </div>
      ) : null}
      <AbsoluteFill style={{boxShadow: `inset 0 0 0 10px ${palette.accent}`}} />
    </AbsoluteFill>
  );
};

export const Thumbnail: React.FC<ThumbnailProps> = (p) => (
  <LayoutProvider layout={{...LAYOUT_LANDSCAPE, width: p.width, height: p.height}}>
    <ThemeProvider theme={p.theme}>
      <Inner {...p} />
    </ThemeProvider>
  </LayoutProvider>
);
