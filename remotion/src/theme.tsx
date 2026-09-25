import React, {createContext, useContext, useEffect, useState} from 'react';
import {cancelRender, continueRender, delayRender, staticFile} from 'remotion';
import {Theme} from './types';

export const HEADING = "'SeriesHeading', 'Montserrat', 'Segoe UI', sans-serif";
export const BODY = "'SeriesBody', 'Inter', 'Segoe UI', sans-serif";

// Sabit, birbiriyle çakışmayan ekran bölgeleri (1080x1920), yukarıdan aşağı:
//   rozet 56-132 | logo çipleri 168-298 | sahne içeriği 170/340-1200 | altyazı 1250-1510
// Alt ~%20 YouTube arayüzünün altında kalır. Sahne katmanı (zoom dahil) rozet ve
// çip bölgelerine taşamaz: SceneFrame üst kenarı kırpar.
const BADGE_TOP = 56;
const BADGE_HEIGHT = 76;
const CHIPS_TOP = 168;
const CHIPS_HEIGHT = 130;
export const LAYOUT = {
  badgeTop: BADGE_TOP,
  badgeHeight: BADGE_HEIGHT,
  chipsTop: CHIPS_TOP,
  chipsHeight: CHIPS_HEIGHT,
  // Sahne katmanının görünür üst sınırı (çip varsa/yoksa).
  sceneClipTopWithChips: CHIPS_TOP + CHIPS_HEIGHT + 16,
  sceneClipTop: BADGE_TOP + BADGE_HEIGHT + 16,
  contentTopWithChips: 340,
  contentTop: 170,
  contentBottom: 1200,
  captionTop: 1250,
  captionHeight: 260,
  sidePadding: 70,
};

const ThemeContext = createContext<Theme | null>(null);

export const ThemeProvider: React.FC<{theme: Theme; children: React.ReactNode}> = ({theme, children}) => {
  const [handle] = useState(() => delayRender('Seri fontları yükleniyor'));
  useEffect(() => {
    const faces: FontFace[] = [];
    if (theme.headingFont) faces.push(new FontFace('SeriesHeading', `url(${staticFile(theme.headingFont)})`, {weight: '100 900'}));
    if (theme.bodyFont) faces.push(new FontFace('SeriesBody', `url(${staticFile(theme.bodyFont)})`, {weight: '100 900'}));
    Promise.all(faces.map((f) => f.load()))
      .then((loaded) => {
        loaded.forEach((f) => (document.fonts as unknown as {add: (f: FontFace) => void}).add(f));
        continueRender(handle);
      })
      .catch((err) => cancelRender(err));
  }, [handle, theme.bodyFont, theme.headingFont]);
  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
};

export const useTheme = (): Theme => {
  const t = useContext(ThemeContext);
  if (!t) throw new Error('ThemeProvider eksik');
  return t;
};

// "44,6" / "125" / "1.000" / "%90" gibi Türkçe yazılmış değerleri sayaç için ayrıştırır.
export const parseNumber = (value: string) => {
  const m = value.trim().match(/^([^\d]*)([\d.,]+)(.*)$/);
  if (!m) return null;
  const [, prefix, raw, suffix] = m;
  let normalized: string;
  let decimals = 0;
  if (raw.includes(',')) {
    normalized = raw.replace(/\./g, '').replace(',', '.');
    decimals = raw.split(',')[1]?.length ?? 0;
  } else if (/^\d{1,3}(\.\d{3})+$/.test(raw)) {
    normalized = raw.replace(/\./g, '');
  } else {
    normalized = raw;
    decimals = raw.includes('.') ? raw.split('.')[1].length : 0;
  }
  const num = Number(normalized);
  if (!Number.isFinite(num)) return null;
  return {prefix, num, decimals, suffix};
};

export const formatNumber = (num: number, decimals: number) =>
  num.toLocaleString('tr-TR', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
