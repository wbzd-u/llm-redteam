import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#7dd3fc" },
    secondary: { main: "#a78bfa" },
    background: { default: "#0b1020", paper: "#11182b" },
  },
  shape: { borderRadius: 10 },
  typography: { fontFamily: "Inter, Segoe UI, Arial, sans-serif" },
});
