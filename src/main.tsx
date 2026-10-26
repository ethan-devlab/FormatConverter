import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  FluentProvider,
  createLightTheme,
  type BrandVariants,
} from "@fluentui/react-components";
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/nunito-sans";
import "@fontsource/noto-sans-tc/400.css";
import "@fontsource/noto-sans-tc/600.css";
import "./i18n";
import "./styles.css";
import App from "./App";

const clay: BrandVariants = {
  10: "#1e0803",
  20: "#34130b",
  30: "#4b2014",
  40: "#622b1c",
  50: "#793723",
  60: "#8c422c",
  70: "#98482f",
  80: "#a34f37",
  90: "#b1664e",
  100: "#c17d65",
  110: "#ce9783",
  120: "#dcb3a2",
  130: "#e8c9bc",
  140: "#f0dcd2",
  150: "#f7eae3",
  160: "#fcf4ee",
};
const theme = createLightTheme(clay);
theme.fontFamilyBase =
  '"Nunito Sans Variable", "Noto Sans TC", system-ui, sans-serif';
theme.fontFamilyNumeric = theme.fontFamilyBase;
theme.borderRadiusMedium = "8px";
theme.borderRadiusLarge = "12px";
theme.colorNeutralBackground1 = "oklch(1 0 0)";
theme.colorNeutralForeground1 = "oklch(0.2603 0.0105 61)";
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <FluentProvider theme={theme}>
      <App />
    </FluentProvider>
  </StrictMode>,
);
