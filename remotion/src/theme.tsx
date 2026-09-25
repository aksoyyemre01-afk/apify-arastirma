import React, {createContext, useContext, useEffect, useState} from 'react';
import {cancelRender, continueRender, delayRender, staticFile} from 'remotion';
import {Theme} from './types';

export const HEADING = "'SeriesHeading', 'Montserrat', 'Segoe UI', sans-serif";
export const BODY = "'SeriesBody', 'Inter', 'Segoe UI', sans-serif";

// Ekran bölgeleri (1080x1920). Alt ~%20 YouTube arayüzünün altında kalır;
// sahne içeriği CONTENT bandında, altyazı CAPTION bandında durur.
export const LAYOUT = {
  badgeTop: 70,
  contentTop: 200,
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
