import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#38bdf8" },
    success: { main: "#4ade80" },
    background: { default: "#0a1020", paper: "#111a2d" },
    divider: "rgba(148, 163, 184, 0.18)",
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: "'Microsoft YaHei UI', 'PingFang SC', 'Segoe UI', sans-serif",
    h3: { fontWeight: 700, letterSpacing: "-0.035em" },
    h4: { fontWeight: 700, letterSpacing: "-0.025em" },
    h5: { fontWeight: 650 },
    h6: { fontWeight: 650 },
  },
  components: {
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
    MuiButton: { styleOverrides: { root: { textTransform: "none", fontWeight: 650, borderRadius: 9 } } },
    MuiTableCell: { styleOverrides: { head: { fontWeight: 700, color: "#cbd5e1" } } },
  },
});
