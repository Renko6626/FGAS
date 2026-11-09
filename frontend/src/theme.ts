import type { GlobalThemeOverrides } from 'naive-ui';

export const workspaceTheme: GlobalThemeOverrides = {
  common: {
    primaryColor: '#29323e', primaryColorHover: '#46566b', primaryColorPressed: '#202a36', primaryColorSuppl: '#29323e',
    successColor: '#53816b', warningColor: '#9b6a24', errorColor: '#b0443c',
    textColorBase: '#252a32', textColor1: '#252a32', textColor2: '#566477', textColor3: '#85909e',
    borderColor: '#dfe4eb', borderRadius: '5px',
    fontFamily: 'system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif', fontSize: '13px',
  },
  Button: { fontWeight: '500', paddingMedium: '0 12px', paddingSmall: '0 10px' },
  Card: { borderRadius: '6px', paddingMedium: '20px' },
};
