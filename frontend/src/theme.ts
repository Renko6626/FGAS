import type { GlobalThemeOverrides } from "naive-ui";

export const workspaceTheme: GlobalThemeOverrides = {
  common: {
    primaryColor: "#000000",
    primaryColorHover: "#444444",
    primaryColorPressed: "#222222",
    primaryColorSuppl: "#000000",
    successColor: "#387454",
    warningColor: "#9b6a24",
    errorColor: "#b0443c",
    textColorBase: "#000000",
    textColor1: "#000000",
    textColor2: "#333333",
    textColor3: "#777777",
    borderColor: "#bcbcbc",
    borderRadius: "0px",
    fontFamily: 'Arial, Helvetica, "Microsoft YaHei", sans-serif',
    fontSize: "14px",
  },
  Button: { fontWeight: "500" },
  Card: { borderRadius: "0px", paddingMedium: "24px" },
};
