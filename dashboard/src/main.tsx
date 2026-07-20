import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Alert, AppBar, Box, Chip, CircularProgress, CssBaseline, Divider, Drawer,
  List, ListItemButton, ListItemIcon, ListItemText, Paper, Stack, Toolbar,
  Typography, ThemeProvider, Button, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Tabs, Tab,
} from "@mui/material";
import DashboardRoundedIcon from "@mui/icons-material/DashboardRounded";
import FolderOpenRoundedIcon from "@mui/icons-material/FolderOpenRounded";
import ScienceRoundedIcon from "@mui/icons-material/ScienceRounded";
import HubRoundedIcon from "@mui/icons-material/HubRounded";
import PlayCircleOutlineRoundedIcon from "@mui/icons-material/PlayCircleOutlineRounded";
import { BarChart } from "@mui/x-charts/BarChart";
import { api } from "./api";
import { theme } from "./theme";
import type { CaseDetail, CaseRow, Overview, ResearchSummary } from "./types";

const drawerWidth = 252;
type Page = "overview" | "cases" | "research";

function Metric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return <Paper variant="outlined" sx={{ p: 2, minWidth: 170, flex: "1 1 170px" }}>
    <Typography variant="body2" color="text.secondary">{label}</Typography>
    <Typography variant="h4" sx={{ mt: 0.5 }}>{value}</Typography>
    <Typography variant="caption" color="text.secondary">{detail}</Typography>
  </Paper>;
}

function StatusChip({ value }: { value: string }) {
  const color = value === "confirmed" ? "success" : value === "failed" || value === "halted" ? "warning" : "default";
  return <Chip size="small" label={value} color={color} variant={color === "default" ? "outlined" : "filled"} />;
}

function CountChart({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data);
  return <Paper variant="outlined" sx={{ p: 2, minHeight: 300 }}>
    <Typography variant="subtitle1" sx={{ mb: 1 }}>{title}</Typography>
    {entries.length === 0 ? <Typography color="text.secondary">No recorded data.</Typography> :
      <BarChart
        height={235}
        layout="horizontal"
        yAxis={[{ data: entries.map(([label]) => label), scaleType: "band" }]}
        series={[{ data: entries.map(([, value]) => value), color: "#7dd3fc" }]}
        margin={{ left: 100, right: 20, top: 10, bottom: 20 }}
      />}
  </Paper>;
}

function OverviewPage({ overview, selectCase }: { overview: Overview; selectCase: (id: string) => void }) {
  const totals = overview.summary.totals;
  return <Stack spacing={3}>
    <Box><Typography variant="h4">Research overview</Typography><Typography color="text.secondary">Evidence-first view of the local workbench.</Typography></Box>
    <Stack direction="row" flexWrap="wrap" gap={2}>
      <Metric label="Cases" value={totals.cases} detail={`${totals.attempts} recorded attempts`} />
      <Metric label="Confirmed" value={`${(totals.confirmed_case_rate * 100).toFixed(0)}%`} detail={`${totals.confirmed_cases} cases with verified runtime evidence`} />
      <Metric label="Reproduced" value={`${(totals.reproduced_case_rate * 100).toFixed(0)}%`} detail={`${totals.reproduced_cases} confirmed cases repeated twice`} />
      <Metric label="Campaigns" value={totals.campaigns} detail={`Observed cost: ${totals.observed_cost}`} />
    </Stack>
    <Stack direction={{ xs: "column", lg: "row" }} spacing={2}>
      <Box flex={1}><CountChart title="Cases by target" data={overview.summary.cases_by_target} /></Box>
      <Box flex={1}><CountChart title="Attempts by outcome" data={overview.summary.attempts_by_outcome} /></Box>
    </Stack>
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle1" sx={{ mb: 1 }}>Recent cases</Typography>
      <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Case</TableCell><TableCell>Target</TableCell><TableCell>Stage</TableCell><TableCell align="right">Attempts</TableCell></TableRow></TableHead>
      <TableBody>{overview.recent_cases.map((row) => <TableRow hover key={row.case_id} sx={{ cursor: "pointer" }} onClick={() => selectCase(row.case_id)}><TableCell>{row.title}</TableCell><TableCell>{row.target}</TableCell><TableCell><StatusChip value={row.stage} /></TableCell><TableCell align="right">{row.attempt_count}</TableCell></TableRow>)}</TableBody></Table></TableContainer>
    </Paper>
  </Stack>;
}

function CasesPage({ rows, selectCase }: { rows: CaseRow[]; selectCase: (id: string) => void }) {
  return <Stack spacing={3}><Box><Typography variant="h4">Case workbench</Typography><Typography color="text.secondary">Select a case to inspect its intake, evidence and execution history.</Typography></Box>
    <Paper variant="outlined"><TableContainer><Table><TableHead><TableRow><TableCell>Title</TableCell><TableCell>Target</TableCell><TableCell>Carrier</TableCell><TableCell>Language</TableCell><TableCell>Stage</TableCell><TableCell align="right">Attempts</TableCell><TableCell align="right">Campaigns</TableCell></TableRow></TableHead>
      <TableBody>{rows.map((row) => <TableRow hover key={row.case_id} sx={{ cursor: "pointer" }} onClick={() => selectCase(row.case_id)}><TableCell><Typography fontWeight={500}>{row.title}</Typography><Typography variant="caption" color="text.secondary">{row.case_id}</Typography></TableCell><TableCell>{row.target}</TableCell><TableCell>{row.carrier}</TableCell><TableCell>{row.language}</TableCell><TableCell><StatusChip value={row.stage} /></TableCell><TableCell align="right">{row.attempt_count}</TableCell><TableCell align="right">{row.campaign_count}</TableCell></TableRow>)}</TableBody>
    </Table></TableContainer></Paper></Stack>;
}

function DetailPage({ detail, close }: { detail: CaseDetail; close: () => void }) {
  const [tab, setTab] = useState(0);
  const sections = [
    <Stack spacing={2} key="intake"><Typography variant="h6">{detail.title}</Typography><Typography>{detail.challenge || "No challenge text recorded."}</Typography><Divider /><Typography variant="subtitle2">Authorization scope</Typography><Typography color="text.secondary">{detail.intake?.authorization_scope || "Not recorded"}</Typography><Typography variant="subtitle2">Success criteria</Typography>{(detail.intake?.success_criteria ?? []).map((item) => <Typography key={item}>• {item}</Typography>)}</Stack>,
    <Stack spacing={1} key="evidence">{detail.evidence.length ? detail.evidence.map((item) => <Paper key={item.evidence_id} variant="outlined" sx={{ p: 1.5 }}><Stack direction="row" justifyContent="space-between"><Typography>{item.description}</Typography><StatusChip value={item.verified ? "verified" : "unverified"} /></Stack><Typography variant="caption" color="text.secondary">{item.kind} · {item.source}</Typography></Paper>) : <Typography color="text.secondary">No evidence recorded.</Typography>}</Stack>,
    <Stack spacing={1} key="plans">{detail.plans.length ? detail.plans.map((item) => <Paper key={item.plan_id} variant="outlined" sx={{ p: 1.5 }}><Stack direction="row" justifyContent="space-between"><Typography>{item.planner}</Typography><StatusChip value={item.status} /></Stack><Typography variant="caption" color="text.secondary">{item.steps.length} planned step(s)</Typography></Paper>) : <Typography color="text.secondary">No plans recorded.</Typography>}</Stack>,
    <Stack spacing={1} key="campaigns">{detail.campaigns.length ? detail.campaigns.map((item) => <Paper key={item.campaign_id} variant="outlined" sx={{ p: 1.5 }}><Stack direction="row" justifyContent="space-between"><Typography>{item.target_kind}</Typography><StatusChip value={item.status} /></Stack><Typography variant="caption" color="text.secondary">{item.executed_turns} turns · {item.stop_reason}</Typography></Paper>) : <Typography color="text.secondary">No campaigns recorded.</Typography>}</Stack>,
  ];
  return <Stack spacing={2}><Button onClick={close} sx={{ alignSelf: "flex-start" }}>← Back to cases</Button><Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable"><Tab label="Intake" /><Tab label={`Evidence (${detail.evidence.length})`} /><Tab label={`Plans (${detail.plans.length})`} /><Tab label={`Campaigns (${detail.campaigns.length})`} /></Tabs><Paper variant="outlined" sx={{ p: 2 }}>{sections[tab]}</Paper></Stack>;
}

function ResearchPage({ summary }: { summary: ResearchSummary }) {
  return <Stack spacing={3}><Box><Typography variant="h4">Research analytics</Typography><Typography color="text.secondary">Aggregates exclude raw prompt and response content.</Typography></Box><Stack direction={{ xs: "column", lg: "row" }} spacing={2}><Box flex={1}><CountChart title="Cases by carrier" data={summary.cases_by_carrier} /></Box><Box flex={1}><CountChart title="Campaigns by status" data={summary.campaigns_by_status} /></Box></Stack><Stack direction={{ xs: "column", lg: "row" }} spacing={2}><Box flex={1}><CountChart title="Cases by language tag" data={summary.cases_by_language} /></Box><Box flex={1}><CountChart title="Mechanism link relations" data={summary.mechanism_links_by_relation} /></Box></Stack></Stack>;
}

function App() {
  const [page, setPage] = useState<Page>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [research, setResearch] = useState<ResearchSummary | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = async () => { try { setError(null); const [nextOverview, nextCases, nextResearch] = await Promise.all([api.overview(), api.cases(), api.research()]); setOverview(nextOverview); setCases(nextCases); setResearch(nextResearch); } catch (err) { setError(err instanceof Error ? err.message : "Could not load local API"); } };
  useEffect(() => { void load(); }, []);
  const selectCase = async (caseId: string) => { try { setDetail(await api.caseDetail(caseId)); } catch (err) { setError(err instanceof Error ? err.message : "Could not load case"); } };
  const nav = useMemo(() => [
    ["overview", "Overview", <DashboardRoundedIcon />], ["cases", "Cases", <FolderOpenRoundedIcon />], ["research", "Research", <ScienceRoundedIcon />],
  ] as const, []);
  return <ThemeProvider theme={theme}><CssBaseline /><Box sx={{ display: "flex", minHeight: "100vh" }}><AppBar position="fixed" elevation={0} sx={{ zIndex: (value) => value.zIndex.drawer + 1, borderBottom: 1, borderColor: "divider" }}><Toolbar><HubRoundedIcon sx={{ mr: 1.5 }} /><Typography variant="h6" sx={{ flexGrow: 1 }}>LLM Red Team Workbench</Typography><Button color="inherit" onClick={() => void load()}>Refresh</Button></Toolbar></AppBar><Drawer variant="permanent" sx={{ width: drawerWidth, flexShrink: 0, "& .MuiDrawer-paper": { width: drawerWidth, boxSizing: "border-box", borderRight: 1, borderColor: "divider" } }}><Toolbar /><List>{nav.map(([key, label, icon]) => <ListItemButton key={key} selected={page === key && !detail} onClick={() => { setDetail(null); setPage(key); }}><ListItemIcon>{icon}</ListItemIcon><ListItemText primary={label} /></ListItemButton>)}</List><Divider /><Box sx={{ p: 2 }}><Typography variant="caption" color="text.secondary">Local-only dashboard<br />API: 127.0.0.1:8787</Typography></Box></Drawer><Box component="main" sx={{ flexGrow: 1, p: { xs: 2, md: 4 }, pt: { xs: 11, md: 12 }, maxWidth: 1600, width: "100%" }}>{error && <Alert severity="error" sx={{ mb: 2 }}>{error}. Start the local API with <code>python -m redteam_memory serve</code>.</Alert>}{!overview || !research ? <Box sx={{ display: "grid", placeItems: "center", minHeight: 300 }}><CircularProgress /></Box> : detail ? <DetailPage detail={detail} close={() => setDetail(null)} /> : page === "overview" ? <OverviewPage overview={overview} selectCase={selectCase} /> : page === "cases" ? <CasesPage rows={cases} selectCase={selectCase} /> : <ResearchPage summary={research} />}</Box></Box></ThemeProvider>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
