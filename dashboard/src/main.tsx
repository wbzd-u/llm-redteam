import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Alert, AppBar, Box, Button, Checkbox, Chip, CircularProgress, CssBaseline, Dialog,
  DialogActions, DialogContent, DialogTitle, Divider, Drawer, Grid, List,
  FormControlLabel, ListItemButton, ListItemIcon, ListItemText, Paper, Stack, Tab, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, Tabs, Toolbar,
  TextField, ToggleButton, ToggleButtonGroup, Typography, ThemeProvider,
} from "@mui/material";
import AddTaskRoundedIcon from "@mui/icons-material/AddTaskRounded";
import ArrowBackRoundedIcon from "@mui/icons-material/ArrowBackRounded";
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import DashboardRoundedIcon from "@mui/icons-material/DashboardRounded";
import FactCheckRoundedIcon from "@mui/icons-material/FactCheckRounded";
import FolderOpenRoundedIcon from "@mui/icons-material/FolderOpenRounded";
import HubRoundedIcon from "@mui/icons-material/HubRounded";
import MenuBookRoundedIcon from "@mui/icons-material/MenuBookRounded";
import PlayCircleOutlineRoundedIcon from "@mui/icons-material/PlayCircleOutlineRounded";
import ScienceRoundedIcon from "@mui/icons-material/ScienceRounded";
import { BarChart } from "@mui/x-charts/BarChart";
import { api } from "./api";
import { theme } from "./theme";
import type { CaseDetail, CaseRow, ExecutionArtifacts, Overview, PaperPacket, ResearchSummary, TaskWorkspace } from "./types";

const drawerWidth = 256;
type Page = "home" | "cases" | "experience" | "research";

const statusLabel: Record<string, string> = {
  confirmed: "历史已通关", probing: "正在探索", baseline: "已建立基线", verification: "等待验证",
  halted: "已暂停", first_refusal: "首次被拒绝", completed: "已完成", budget_exhausted: "预算已用完",
  failed: "未成功", negative: "负例", reported: "历史报告", running: "正在运行", pending: "等待执行", approved: "已批准",
  draft: "草稿", verified: "已验证", unverified: "未验证", unknown: "待整理",
  refused: "被拒绝", error: "出错",
};

function StatusChip({ value }: { value: string }) {
  const color = value === "confirmed" || value === "verified" || value === "completed"
    ? "success" : value === "failed" || value === "halted" || value === "budget_exhausted"
      ? "warning" : "default";
  return <Chip size="small" label={statusLabel[value] ?? value} color={color} variant={color === "default" ? "outlined" : "filled"} />;
}

function experienceFrom(row: CaseRow) {
  const text = `${row.title} ${row.mechanism} ${row.tags.join(" ")}`.toLowerCase();
  if (text.includes("narrative") || text.includes("identity")) return ["叙事与角色边界", "观察角色设定是否会把目标的职责、权限或身份叙事带偏。"];
  if (text.includes("standing") || text.includes("exception") || text.includes("policy")) return ["规则解释与例外边界", "关注系统如何理解规则、例外和优先级；先用无害样本确认边界。"];
  if (text.includes("regex") || text.includes("semantic")) return ["字面规则与语义理解", "对照字面校验和语义意图的差异，记录最小可复现输入。"];
  if (text.includes("template") || text.includes("lamp")) return ["模板与指令层级", "分析模板、上下文和目标行为之间的信任边界。"];
  if (text.includes("key") || text.includes("librarius")) return ["上下文定位与重建", "验证模型会依据哪些上下文片段形成结论，避免凭猜测下结论。"];
  if (text.includes("genie") || text.includes("freedom")) return ["目标重述与约束理解", "测试同一目标在不同表述下，约束是否仍被一致执行。"];
  return [row.mechanism || "待整理机制", "打开案例查看你的原始复盘，再把可复用的规律整理成机制卡。"];
}

function Metric({ label, value, detail, tone = "primary" }: { label: string; value: string | number; detail: string; tone?: "primary" | "success" | "neutral" }) {
  const border = tone === "success" ? "success.main" : tone === "primary" ? "primary.main" : "divider";
  return <Paper variant="outlined" sx={{ p: 2.25, height: "100%", borderTop: 3, borderTopColor: border }}>
    <Typography variant="body2" color="text.secondary">{label}</Typography>
    <Typography variant="h4" sx={{ mt: 0.6, mb: 0.75 }}>{value}</Typography>
    <Typography variant="body2" color="text.secondary">{detail}</Typography>
  </Paper>;
}

function EmptyState({ title, description, action, onAction }: { title: string; description: string; action: string; onAction: () => void }) {
  return <Paper variant="outlined" sx={{ p: 3.5, textAlign: "center", borderStyle: "dashed" }}>
    <AutoAwesomeRoundedIcon color="primary" sx={{ fontSize: 34, mb: 1 }} />
    <Typography variant="h6">{title}</Typography>
    <Typography color="text.secondary" sx={{ mt: 0.75, mb: 2 }}>{description}</Typography>
    <Button variant="contained" onClick={onAction}>{action}</Button>
  </Paper>;
}

function ActionCard({ icon, title, description, action, onAction, emphasis = false }: { icon: React.ReactNode; title: string; description: string; action: string; onAction: () => void; emphasis?: boolean }) {
  return <Paper variant="outlined" sx={{ p: 2.5, height: "100%", display: "flex", flexDirection: "column", alignItems: "flex-start", borderColor: emphasis ? "primary.main" : "divider", background: emphasis ? "linear-gradient(135deg, rgba(56,189,248,.10), rgba(56,189,248,.02))" : undefined }}>
    <Box sx={{ color: "primary.main", mb: 1.75 }}>{icon}</Box>
    <Typography variant="h6">{title}</Typography>
    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75, mb: 2.25, flexGrow: 1 }}>{description}</Typography>
    <Button variant={emphasis ? "contained" : "outlined"} onClick={onAction}>{action}</Button>
  </Paper>;
}

function HomePage({ overview, rows, selectCase, goToCases, goToExperience, openIntake }: { overview: Overview; rows: CaseRow[]; selectCase: (id: string) => void; goToCases: () => void; goToExperience: () => void; openIntake: () => void }) {
  const totals = overview.summary.totals;
  const confirmed = rows.filter((row) => row.status === "confirmed");
  const inProgress = rows.filter((row) => row.status !== "confirmed").slice(0, 3);
  return <Stack spacing={4}>
    <Box sx={{ maxWidth: 760 }}>
      <Typography variant="overline" color="primary.main" fontWeight={700}>个人红队助手</Typography>
      <Typography variant="h3" sx={{ mt: 0.5 }}>从一次通关，变成下一次的经验。</Typography>
      <Typography color="text.secondary" sx={{ mt: 1.25, fontSize: "1.05rem" }}>这里不是模型监控台。它帮你保存通关和失败的关键机制，在新关卡开始时找到相似经验，并把每一步测试变成可复盘的研究记录。</Typography>
    </Box>

    <Grid container spacing={2.25}>
      <Grid size={{ xs: 12, sm: 4 }}><ActionCard icon={<AddTaskRoundedIcon fontSize="large" />} title="导入新关卡" description="粘贴题目、授权范围和成功判据。导入后会自动从你的经验中寻找相似机制。" action="查看导入方式" onAction={openIntake} emphasis /></Grid>
      <Grid size={{ xs: 12, sm: 4 }}><ActionCard icon={<PlayCircleOutlineRoundedIcon fontSize="large" />} title="继续一个案例" description={inProgress.length ? `你有 ${inProgress.length} 个待推进案例，可以继续记录测试和结果。` : "当前没有正在推进的案例。先导入一个关卡，系统会为它建立工作区。"} action={inProgress.length ? "查看待推进案例" : "查看我的案例"} onAction={goToCases} /></Grid>
      <Grid size={{ xs: 12, sm: 4 }}><ActionCard icon={<MenuBookRoundedIcon fontSize="large" />} title="复盘通关经验" description={`你的知识库中已有 ${confirmed.length} 条历史已通关案例，适合先整理出可迁移的机制。`} action="打开经验库" onAction={goToExperience} /></Grid>
    </Grid>

    <Grid container spacing={2.25}>
      <Grid size={{ xs: 12, lg: 8 }}>
        <Paper variant="outlined" sx={{ p: { xs: 2.25, md: 3 }, height: "100%" }}>
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "center" }} gap={1.5} sx={{ mb: 2.5 }}>
            <Box><Typography variant="h5">建议从这里开始</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>先选一个明确动作，减少在“看数据”和“真正推进关卡”之间来回切换。</Typography></Box>
            <Chip label="按你的本地知识库" color="primary" variant="outlined" />
          </Stack>
          {inProgress.length ? <Stack spacing={1.25}>{inProgress.map((row) => <Paper key={row.case_id} variant="outlined" sx={{ p: 1.5, display: "flex", gap: 1.5, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}><Box><Typography fontWeight={600}>{row.title}</Typography><Typography variant="body2" color="text.secondary">下一步：查看已记录的题目、对话和计划。</Typography></Box><Button variant="contained" onClick={() => selectCase(row.case_id)}>继续</Button></Paper>)}</Stack> : <EmptyState title="当前没有正在推进的关卡" description="导入一题后，我会把题目与历史经验匹配，并帮你建立从分析到复盘的工作区。" action="查看导入方式" onAction={openIntake} />}
        </Paper>
      </Grid>
      <Grid size={{ xs: 12, lg: 4 }}>
        <Stack spacing={2.25} height="100%">
          <Metric label="历史通关经验" value={totals.historical_confirmed_cases} detail="来自你的本地复盘记录" tone="success" />
          <Metric label="已整理的个人案例" value={totals.user_kb_cases} detail="不把公开种子混入首页" tone="primary" />
          <Metric label="运行时验证证据" value={totals.confirmed_cases} detail="只有平台或执行记录可验证时才计入" tone="neutral" />
        </Stack>
      </Grid>
    </Grid>

  </Stack>;
}

function CasesPage({ rows, selectCase }: { rows: CaseRow[]; selectCase: (id: string) => void }) {
  const sorted = [...rows].sort((a, b) => Number(a.status === "confirmed") - Number(b.status === "confirmed") || b.case_id.localeCompare(a.case_id));
  return <Stack spacing={3}>
    <Box><Typography variant="h4">我的案例</Typography><Typography color="text.secondary" sx={{ mt: 0.75 }}>这里保存题目、尝试、证据和复盘。点击一条案例查看完整工作区。</Typography></Box>
    <Paper variant="outlined"><TableContainer><Table><TableHead><TableRow><TableCell>案例</TableCell><TableCell>目标</TableCell><TableCell>当前状态</TableCell><TableCell align="right">尝试</TableCell><TableCell align="right">证据</TableCell><TableCell /></TableRow></TableHead>
      <TableBody>{sorted.map((row) => <TableRow hover key={row.case_id}><TableCell><Typography fontWeight={600}>{row.title}</Typography><Typography variant="caption" color="text.secondary">{row.carrier || "载体未记录"} · {row.language || "语言未记录"}</Typography></TableCell><TableCell>{row.target || "未记录"}</TableCell><TableCell><StatusChip value={row.status} /></TableCell><TableCell align="right">{row.attempt_count}</TableCell><TableCell align="right">{row.evidence_count}</TableCell><TableCell align="right"><Button size="small" onClick={() => selectCase(row.case_id)}>打开</Button></TableCell></TableRow>)}</TableBody>
    </Table></TableContainer></Paper>
  </Stack>;
}

function ExperiencePage({ rows, goToCases }: { rows: CaseRow[]; goToCases: () => void }) {
  const confirmed = rows.filter((row) => row.status === "confirmed");
  const mechanisms = Array.from(confirmed.reduce((groups, row) => {
    const [name, reuse] = experienceFrom(row);
    const current = groups.get(name) ?? { name, reuse, count: 0 };
    current.count += 1;
    groups.set(name, current);
    return groups;
  }, new Map<string, { name: string; reuse: string; count: number }>()).values());
  return <Stack spacing={3}>
    <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", md: "center" }} gap={2}><Box><Typography variant="h4">我的经验</Typography><Typography color="text.secondary" sx={{ mt: 0.75 }}>这里是从历史案例抽取出的“可复用规律”，不是第二份案例列表。所有原始记录只在“我的案例”中维护。</Typography></Box><Button variant="outlined" onClick={goToCases}>查看原始案例</Button></Stack>
    {mechanisms.length ? <><Paper variant="outlined" sx={{ p: 2.25 }}><Typography variant="body2" color="text.secondary">当前由 {confirmed.length} 条历史通关记录归纳出 {mechanisms.length} 类经验。每类经验应继续用新的独立案例、负例和运行时证据验证。</Typography></Paper><Grid container spacing={2.25}>{mechanisms.map((item) => <Grid key={item.name} size={{ xs: 12, md: 6, xl: 4 }}><Paper variant="outlined" sx={{ p: 2.25, height: "100%", display: "flex", flexDirection: "column" }}><Typography variant="caption" color="text.secondary">自动归纳的机制</Typography><Typography variant="h6" sx={{ mt: 0.5 }}>{item.name}</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 1, flexGrow: 1 }}>{item.reuse}</Typography><Chip size="small" label={`来自 ${item.count} 条历史通关`} color="success" variant="outlined" sx={{ mt: 2, alignSelf: "flex-start" }} /></Paper></Grid>)}</Grid></> : <EmptyState title="经验库还在等待第一条记录" description="导入或整理一个已完成案例后，系统会从案例复盘中归纳机制。" action="查看我的案例" onAction={goToCases} />}
  </Stack>;
}

function chartSeries(data: Record<string, number>, limit = 8) {
  const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
  if (sorted.length <= limit) return sorted;
  const visible = sorted.slice(0, limit);
  return [...visible, ["其他", sorted.slice(limit).reduce((total, [, value]) => total + value, 0)] as [string, number]];
}

function CountChart({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = chartSeries(data);
  return <Paper variant="outlined" sx={{ p: 2.25, minHeight: 300 }}><Typography variant="subtitle1" fontWeight={600}>{title}</Typography>
    {entries.length === 0 ? <Typography color="text.secondary" sx={{ mt: 3 }}>暂时没有可分析的数据。</Typography> : <BarChart height={Math.max(235, entries.length * 34)} layout="horizontal" yAxis={[{ data: entries.map(([label]) => label), scaleType: "band" }]} series={[{ data: entries.map(([, value]) => value), color: "#38bdf8" }]} margin={{ left: 110, right: 20, top: 16, bottom: 20 }} />}
  </Paper>;
}

function CrossTabTable({ title, subtitle, table }: { title: string; subtitle: string; table: { columns: string[]; rows: Array<{ label: string; total: number; values: Record<string, number> }> } }) {
  return <Paper variant="outlined" sx={{ p: 2.25, height: "100%" }}>
    <Typography variant="h6">{title}</Typography>
    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.5 }}>{subtitle}</Typography>
    {table.rows.length ? <TableContainer><Table size="small"><TableHead><TableRow><TableCell>机制 / 分组</TableCell>{table.columns.map((column) => <TableCell key={column} align="right">{statusLabel[column] ?? column}</TableCell>)}<TableCell align="right">合计</TableCell></TableRow></TableHead><TableBody>{table.rows.map((row) => <TableRow key={row.label}><TableCell>{row.label}</TableCell>{table.columns.map((column) => <TableCell key={column} align="right">{row.values[column] ?? 0}</TableCell>)}<TableCell align="right">{row.total}</TableCell></TableRow>)}</TableBody></Table></TableContainer> : <Typography color="text.secondary">尚无机制关联记录。先把案例关联到机制卡，统计表会自动生成。</Typography>}
  </Paper>;
}

function downloadText(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function confidenceLabel(value: string) {
  return ({ confirmed: "已确认", observed: "已观察", hypothesis: "待验证", unclassified: "待整理" } as Record<string, string>)[value] ?? value;
}

function ResearchPage({ summary, packet }: { summary: ResearchSummary; packet: PaperPacket }) {
  const [tab, setTab] = useState(0);
  const coverage = Object.entries(packet.readiness.field_coverage);
  const matrix = packet.mechanism_matrix;
  const content = [
    <Stack spacing={3} key="mechanisms">
      <Paper variant="outlined" sx={{ p: { xs: 2.25, md: 3 }, borderLeft: 4, borderLeftColor: "primary.main" }}>
        <Typography variant="overline" color="primary.main" fontWeight={700}>研究问题起点</Typography>
        <Typography variant="h5" sx={{ mt: 0.4 }}>哪些机制会在什么条件下改变系统行为？</Typography>
        <Typography color="text.secondary" sx={{ mt: 1 }}>从机制卡开始，而不是从单条输入开始。每张卡都有适用信号、前提、负信号和历史案例关系，可用于提出可证伪的实验假设。</Typography>
      </Paper>
      <Grid container spacing={2.25}>{matrix.map((item) => <Grid key={item.mechanism_id} size={{ xs: 12, md: 6, xl: 4 }}><Paper variant="outlined" sx={{ p: 2.25, height: "100%", display: "flex", flexDirection: "column" }}>
        <Stack direction="row" justifyContent="space-between" gap={1} alignItems="flex-start"><Box><Typography variant="subtitle1" fontWeight={700}>{item.name}</Typography><Typography variant="caption" color="text.secondary">{item.category}</Typography></Box><Chip size="small" label={confidenceLabel(item.confidence)} color={item.confidence === "observed" ? "primary" : "default"} variant={item.confidence === "observed" ? "filled" : "outlined"} /></Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1.25, flexGrow: 1 }}>{item.summary}</Typography>
        <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: "wrap", rowGap: 1 }}><Chip size="small" label={`${item.case_count} 个案例`} variant="outlined" /><Chip size="small" label={`历史通关 ${item.confirmed_cases}`} color="success" variant="outlined" /><Chip size="small" label={`负例 ${item.negative_cases}`} variant="outlined" /></Stack>
        {item.applicability_signals[0] && <Box sx={{ mt: 1.5 }}><Typography variant="caption" color="text.secondary">适用信号</Typography><Typography variant="body2">{item.applicability_signals[0]}</Typography></Box>}
        {item.negative_signals[0] && <Box sx={{ mt: 1.1 }}><Typography variant="caption" color="text.secondary">排除信号</Typography><Typography variant="body2">{item.negative_signals[0]}</Typography></Box>}
      </Paper></Grid>)}</Grid>
    </Stack>,
    <Stack spacing={3} key="data">
      <Paper variant="outlined" sx={{ p: { xs: 2.25, md: 3 } }}><Typography variant="h5">论文数据准备度</Typography><Typography color="text.secondary" sx={{ mt: 0.75 }}>这不是给数据“打高分”，而是明确哪些字段已经能写进方法，哪些还需要补实验。</Typography><Grid container spacing={2} sx={{ mt: 1 }}>{coverage.map(([label, value]) => <Grid key={label} size={{ xs: 6, md: 4, xl: 3 }}><Metric label={label} value={`${Math.round(value.rate * 100)}%`} detail={`${value.filled} / ${value.total} 个案例已记录`} tone={value.rate >= 0.75 ? "success" : "neutral"} /></Grid>)}</Grid></Paper>
      <Grid container spacing={2.25}><Grid size={{ xs: 12, lg: 7 }}><Paper variant="outlined" sx={{ p: 2.25, height: "100%" }}><Typography variant="h6">数据字典</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.5 }}>这些字段就是论文方法、附录和公开复现实验表的共同语言。</Typography><TableContainer><Table size="small"><TableHead><TableRow><TableCell>字段</TableCell><TableCell>含义</TableCell><TableCell>单位</TableCell></TableRow></TableHead><TableBody>{packet.data_dictionary.map((item) => <TableRow key={item.field}><TableCell><Typography component="code" variant="body2">{item.field}</Typography></TableCell><TableCell>{item.meaning}</TableCell><TableCell>{item.unit}</TableCell></TableRow>)}</TableBody></Table></TableContainer></Paper></Grid><Grid size={{ xs: 12, lg: 5 }}><Paper variant="outlined" sx={{ p: 2.25, height: "100%" }}><Typography variant="h6">下一批需要补的数据</Typography><Stack spacing={1.25} sx={{ mt: 1.5 }}>{packet.readiness.gaps.length ? packet.readiness.gaps.map((gap) => <Stack key={gap} direction="row" spacing={1} alignItems="flex-start"><AutoAwesomeRoundedIcon color="primary" fontSize="small" sx={{ mt: 0.25 }} /><Typography variant="body2">{gap}</Typography></Stack>) : <Typography color="text.secondary">当前数据满足基础描述性分析。仍应在论文中说明样本选择和外推边界。</Typography>}</Stack></Paper></Grid></Grid>
      <Grid container spacing={2.25}><Grid size={{ xs: 12, lg: 6 }}><CountChart title="尝试结果分布" data={summary.attempts_by_outcome} /></Grid><Grid size={{ xs: 12, lg: 6 }}><CountChart title="载体分布" data={summary.cases_by_carrier} /></Grid><Grid size={{ xs: 12 }}><Alert severity="info">{packet.cross_tabs.note} 当前共有 {packet.cross_tabs.linked_records} 条机制—案例关联，可作为机制覆盖统计的分母。</Alert></Grid><Grid size={{ xs: 12, xl: 6 }}><CrossTabTable title="机制 × 案例状态" subtitle="检查每个机制是否同时拥有历史通关与负例，避免只从单侧样本归纳规律。" table={packet.cross_tabs.mechanism_by_status} /></Grid><Grid size={{ xs: 12, xl: 6 }}><CrossTabTable title="机制 × 关联证据" subtitle="confirmed、observed、negative 是机制与案例的证据关系，不等同于单次模型自述。" table={packet.cross_tabs.mechanism_by_relation} /></Grid><Grid size={{ xs: 12, xl: 6 }}><CrossTabTable title="机制 × 目标" subtitle="用于判断不同机制是否只在单一目标上出现，避免过早声称跨模型迁移。" table={packet.cross_tabs.mechanism_by_target} /></Grid><Grid size={{ xs: 12, xl: 6 }}><CrossTabTable title="目标 × 载体" subtitle="用于识别哪些目标和载体组合尚未建立对照。" table={packet.cross_tabs.target_by_carrier} /></Grid></Grid>
    </Stack>,
    <Stack spacing={3} key="paper">
      <Paper variant="outlined" sx={{ p: { xs: 2.25, md: 3 } }}><Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={2}><Box><Typography variant="h5">论文数据包</Typography><Typography color="text.secondary" sx={{ mt: 0.75 }}>自动整理方法草稿、机制矩阵、数据字典和局限性。它不会把原始输入或响应导出到这个页面。</Typography></Box><Stack direction="row" gap={1} flexWrap="wrap"><Button variant="outlined" onClick={() => downloadText("redteam-paper-packet.md", packet.markdown, "text/markdown;charset=utf-8")}>下载论文草稿</Button><Button variant="contained" onClick={() => downloadText("redteam-paper-data.json", JSON.stringify(packet, null, 2), "application/json;charset=utf-8")}>下载结构化数据</Button></Stack></Stack></Paper>
      <Paper variant="outlined" sx={{ p: { xs: 2.25, md: 3 } }}><Typography variant="h6">方法部分草稿</Typography><Typography color="text.secondary" sx={{ mt: 1.25, whiteSpace: "pre-wrap", lineHeight: 1.8 }}>{packet.methods_draft}</Typography></Paper>
      <Paper variant="outlined" sx={{ p: { xs: 2.25, md: 3 } }}><Typography variant="h6">机制 × 证据表</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.5 }}>先用这张表检查每个机制是否有正例、负例和可验证证据，再决定哪些适合进入论文主实验。</Typography><TableContainer><Table size="small"><TableHead><TableRow><TableCell>机制</TableCell><TableCell align="right">案例</TableCell><TableCell align="right">历史通关</TableCell><TableCell align="right">负例</TableCell><TableCell align="right">已验证证据</TableCell></TableRow></TableHead><TableBody>{matrix.map((item) => <TableRow key={item.mechanism_id}><TableCell>{item.name}</TableCell><TableCell align="right">{item.case_count}</TableCell><TableCell align="right">{item.confirmed_cases}</TableCell><TableCell align="right">{item.negative_cases}</TableCell><TableCell align="right">{item.verified_evidence_count}</TableCell></TableRow>)}</TableBody></Table></TableContainer></Paper>
    </Stack>,
  ];
  return <Stack spacing={3}><Box><Typography variant="h4">机制研究工作台</Typography><Typography color="text.secondary" sx={{ mt: 0.75 }}>把案例变成机制、把机制变成可复现实验、再把实验变成论文可用的数据和论证。</Typography></Box><Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable"><Tab label={`机制地图 (${matrix.length})`} /><Tab label="数据准备度" /><Tab label="论文数据包" /></Tabs>{content[tab]}</Stack>;
}

function TaskWorkspacePage({ workspace, close, refresh }: { workspace: TaskWorkspace; close: () => void; refresh: () => Promise<void> }) {
  const { task, recommended_mechanisms: mechanisms, next_action: nextAction } = workspace;
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<ExecutionArtifacts | null>(null);
  const [campaignInputs, setCampaignInputs] = useState<Record<string, string>>({});
  const [approvedInputs, setApprovedInputs] = useState<Record<string, boolean>>({});
  const [maxTurns, setMaxTurns] = useState("1");
  const [maxSeconds, setMaxSeconds] = useState("60");
  const [maxCost, setMaxCost] = useState("0");
  const [inputText, setInputText] = useState("");
  const [responseText, setResponseText] = useState("");
  const [mechanism, setMechanism] = useState(mechanisms[0]?.mechanism.name ?? "baseline");
  const [outcome, setOutcome] = useState("unknown");
  const [effect, setEffect] = useState("");
  const [refusal, setRefusal] = useState(false);
  const [evidenceDescription, setEvidenceDescription] = useState("");
  const [evidenceVerified, setEvidenceVerified] = useState(false);
  const saveDraft = async () => { setSaving(true); try { await api.createTaskDraft(task.case_id); setNotice("已生成一份待审核的实验草稿。它不会自动执行。 "); await refresh(); } catch (error) { setNotice(error instanceof Error ? error.message : "生成草稿失败"); } finally { setSaving(false); } };
  const approveDraft = async (planId: string) => { setSaving(true); try { await api.approveTaskPlan(task.case_id, planId); setNotice("计划已批准。下一步可为每个步骤准备经审核的输入，再交给执行器。 "); await refresh(); } catch (error) { setNotice(error instanceof Error ? error.message : "批准计划失败"); } finally { setSaving(false); } };
  const previewArtifacts = async (planId: string) => { setSaving(true); try { setArtifacts(await api.executionArtifacts(task.case_id, planId)); setNotice("已生成执行工件预览：所有输入仍为空，等待你逐步审核填写。 "); } catch (error) { setNotice(error instanceof Error ? error.message : "无法生成执行工件"); } finally { setSaving(false); } };
  const createPendingCampaign = async (planId: string) => { const inputs = (task.plans[0]?.steps ?? []).filter((step) => approvedInputs[step.id] && campaignInputs[step.id]?.trim()).map((step) => ({ step_id: step.id, input: campaignInputs[step.id].trim(), review_note: "reviewed in dashboard" })); if (!inputs.length) { setNotice("请先填写至少一个步骤的输入，并勾选“我已审核”。 "); return; } setSaving(true); try { const result = await api.createTaskCampaign(task.case_id, planId, { target_kind: "replay", max_turns: Number(maxTurns), max_seconds: Number(maxSeconds), max_cost: maxCost.trim() === "" ? null : Number(maxCost), inputs }); setNotice(`已创建待执行 Campaign（${result.reviewed_input_count} 个已审核输入）。它尚未运行。 `); await refresh(); } catch (error) { setNotice(error instanceof Error ? error.message : "创建 Campaign 失败"); } finally { setSaving(false); } };
  const saveObservation = async () => { if (!responseText.trim()) { setNotice("请先记录本轮观察到的响应。 "); return; } setSaving(true); try { await api.addObservation(task.case_id, { input_text: inputText, response_text: responseText, mechanism, outcome, observed_effect: effect, refusal, evidence_description: evidenceDescription, evidence_verified: evidenceVerified }); setNotice("这一轮观察已记录，下一步建议已更新。 "); setInputText(""); setResponseText(""); setEffect(""); setEvidenceDescription(""); setRefusal(false); setEvidenceVerified(false); await refresh(); } catch (error) { setNotice(error instanceof Error ? error.message : "保存观察失败"); } finally { setSaving(false); } };
  const draft = task.plans[0] ?? workspace.suggested_plan;
  const artifactPanel = task.plans[0]?.status === "approved" ? <Paper variant="outlined" sx={{ p: { xs: 2.25, md: 3 }, borderLeft: 4, borderLeftColor: "success.main" }}>
    <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={1.5}><Box><Typography variant="h5">执行工件预览</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>这是把已批准计划交给不同执行工具前的共同契约。它不会自动发送请求，也不包含任何真实输入。</Typography></Box><Button variant="contained" disabled={saving} onClick={() => void previewArtifacts(task.plans[0].plan_id)}>查看执行工件</Button></Stack>
    {artifacts && <Grid container spacing={2} sx={{ mt: 1 }}>
      <Grid size={{ xs: 12, md: 6, xl: 3 }}><Paper variant="outlined" sx={{ p: 1.75, height: "100%" }}><Typography fontWeight={700}>离线重放</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>共 {artifacts.replay.inputs.length} 个步骤；每一步输入均待人工审核。</Typography><Typography variant="caption" color="primary.main" sx={{ display: "block", mt: 1 }}>用于本地复盘与最小化复现</Typography></Paper></Grid>
      <Grid size={{ xs: 12, md: 6, xl: 3 }}><Paper variant="outlined" sx={{ p: 1.75, height: "100%" }}><Typography fontWeight={700}>PyRIT 执行契约</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>在连接前还需要：{artifacts.pyrit.required_local_configuration.join("、")}。</Typography><Typography variant="caption" color="primary.main" sx={{ display: "block", mt: 1 }}>用于受预算控制的已授权目标测试</Typography></Paper></Grid>
      <Grid size={{ xs: 12, md: 6, xl: 3 }}><Paper variant="outlined" sx={{ p: 1.75, height: "100%" }}><Typography fontWeight={700}>Inspect AI 实验样本</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>{artifacts.inspect.samples.length} 个样本槽位，输入均为空。</Typography><Typography variant="caption" color="primary.main" sx={{ display: "block", mt: 1 }}>用于固定条件、可重复的实验</Typography></Paper></Grid>
      <Grid size={{ xs: 12, md: 6, xl: 3 }}><Paper variant="outlined" sx={{ p: 1.75, height: "100%" }}><Typography fontWeight={700}>Promptfoo 回归清单</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>{artifacts.promptfoo.tests.length} 条待配置测试；模型连接与提示均未填写。</Typography><Typography variant="caption" color="primary.main" sx={{ display: "block", mt: 1 }}>用于版本对比与回归检查</Typography></Paper></Grid>
      <Grid size={{ xs: 12 }}><Alert severity="info">下一步是：为某一个步骤填写并审核测试输入、设定轮数、时间和成本上限，再创建待执行 Campaign。当前页面不会自动运行。</Alert></Grid>
    </Grid>}
    <Divider sx={{ my: 2 }} />
    <Typography variant="h6">审核输入并创建待执行 Campaign</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>每个输入都要由你手工填写并确认。系统只会保存到本地工作区，创建后的状态为“待执行”，不会发出网络请求。</Typography>
    <Grid container spacing={1.5} sx={{ mt: 0.75 }}>{(task.plans[0]?.steps ?? []).map((step) => <Grid size={{ xs: 12, md: 6 }} key={step.id}><Paper variant="outlined" sx={{ p: 1.5 }}><Typography variant="subtitle2">{step.id}：{step.objective}</Typography><TextField label="经人工审核的测试输入" value={campaignInputs[step.id] ?? ""} onChange={(event) => setCampaignInputs((current) => ({ ...current, [step.id]: event.target.value }))} multiline minRows={2} fullWidth sx={{ mt: 1 }} /><FormControlLabel control={<Checkbox checked={Boolean(approvedInputs[step.id])} onChange={(event) => setApprovedInputs((current) => ({ ...current, [step.id]: event.target.checked }))} />} label="我已审核此输入及其预算范围" /></Paper></Grid>)}</Grid>
    <Grid container spacing={1.5} sx={{ mt: 0.75, alignItems: "center" }}><Grid size={{ xs: 12, sm: 4 }}><TextField label="最多轮数" type="number" value={maxTurns} onChange={(event) => setMaxTurns(event.target.value)} fullWidth /></Grid><Grid size={{ xs: 12, sm: 4 }}><TextField label="最长时间（秒）" type="number" value={maxSeconds} onChange={(event) => setMaxSeconds(event.target.value)} fullWidth /></Grid><Grid size={{ xs: 12, sm: 4 }}><TextField label="最大成本（USD，可为 0）" type="number" value={maxCost} onChange={(event) => setMaxCost(event.target.value)} fullWidth /></Grid><Grid size={{ xs: 12 }}><Button variant="contained" disabled={saving} onClick={() => void createPendingCampaign(task.plans[0].plan_id)}>创建待执行 Campaign</Button></Grid></Grid>
  </Paper> : null;
  return <Stack spacing={3}>
    {artifactPanel}
    <Button startIcon={<ArrowBackRoundedIcon />} onClick={close} sx={{ alignSelf: "flex-start" }}>返回任务列表</Button>
    <Stack direction={{ xs: "column", lg: "row" }} justifyContent="space-between" gap={2}><Box><Typography variant="overline" color="primary.main" fontWeight={700}>任务控制台</Typography><Typography variant="h4">{task.title}</Typography><Typography color="text.secondary" sx={{ mt: 0.75 }}>{task.target || "目标尚未记录"} · {task.carrier || "文本载体"}</Typography></Box><Paper variant="outlined" sx={{ p: 1.75, minWidth: { lg: 330 }, borderLeft: 4, borderLeftColor: "primary.main" }}><Typography variant="caption" color="text.secondary">系统建议的下一步</Typography><Typography fontWeight={700} sx={{ mt: 0.35 }}>{nextAction.action}</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{nextAction.rationale}</Typography></Paper></Stack>
    {notice && <Alert severity={notice.includes("失败") || notice.includes("请先") ? "warning" : "success"} onClose={() => setNotice(null)}>{notice}</Alert>}
    <Grid container spacing={2.25}>
      <Grid size={{ xs: 12, xl: 4 }}><Paper variant="outlined" sx={{ p: 2.25, height: "100%" }}><Typography variant="h6">1. 任务事实</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>先固定目标、题目和判据；这些是后续推理的事实边界。</Typography><Divider sx={{ my: 1.5 }} /><Typography variant="caption" color="text.secondary">题目 / 目标</Typography><Typography variant="body2" sx={{ whiteSpace: "pre-wrap", mt: 0.5 }}>{task.challenge || "尚未补充题目内容。"}</Typography><Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>成功判据</Typography>{task.intake?.success_criteria?.length ? task.intake.success_criteria.map((item) => <Typography variant="body2" key={item}>• {item}</Typography>) : <Typography variant="body2">尚未记录</Typography>}<Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>约束与授权范围</Typography><Typography variant="body2">{task.intake?.authorization_scope || "尚未记录"}</Typography></Paper></Grid>
      <Grid size={{ xs: 12, xl: 4 }}><Paper variant="outlined" sx={{ p: 2.25, height: "100%" }}><Typography variant="h6">2. 机制判断</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.5 }}>来自任务关键词、标签和已关联历史经验的透明匹配，不是无依据的猜测。</Typography>{mechanisms.length ? <Stack spacing={1.25}>{mechanisms.slice(0, 3).map((item) => <Box key={item.mechanism.mechanism_id}><Stack direction="row" justifyContent="space-between" gap={1}><Typography variant="body2" fontWeight={700}>{item.mechanism.name}</Typography><Chip size="small" label={`匹配 ${item.score}`} variant="outlined" /></Stack><Typography variant="caption" color="text.secondary">{item.mechanism.summary}</Typography><Typography variant="caption" color="primary.main" sx={{ display: "block", mt: 0.35 }}>{item.reasons.map((reason) => reason.kind).join(" · ")}</Typography></Box>)}</Stack> : <Typography color="text.secondary">还没有足够的匹配信号。先完善题目与目标信息，或从机制库手动关联。</Typography>}</Paper></Grid>
      <Grid size={{ xs: 12, xl: 4 }}><Paper variant="outlined" sx={{ p: 2.25, height: "100%" }}><Stack direction="row" justifyContent="space-between" gap={1}><Typography variant="h6">3. 实验草稿</Typography>{!task.plans.length && <Button size="small" variant="contained" disabled={saving} onClick={() => void saveDraft()}>生成草稿</Button>}</Stack><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>草稿只定义假设、变量、预期信号和停止条件；需要你审核后才能交给执行层。</Typography><Divider sx={{ my: 1.5 }} />{draft ? <Stack spacing={1.25}>{draft.hypotheses?.map((item: { id: string; statement: string; basis: string; positive_signal: string; negative_signal: string }) => <Box key={item.id}><Typography variant="body2" fontWeight={700}>{item.statement}</Typography><Typography variant="caption" color="text.secondary">依据：{item.basis}</Typography><Typography variant="caption" sx={{ display: "block", mt: 0.35 }}>正信号：{item.positive_signal}</Typography><Typography variant="caption" sx={{ display: "block" }}>负信号：{item.negative_signal}</Typography></Box>)}{task.plans[0]?.status === "draft" && <Button size="small" variant="outlined" disabled={saving} onClick={() => void approveDraft(task.plans[0].plan_id)}>审核后批准计划</Button>}</Stack> : <Typography color="text.secondary">尚无草稿。先生成一个基于当前机制匹配的最小对照实验。</Typography>}</Paper></Grid>
    </Grid>
    <Paper variant="outlined" sx={{ p: 2.25, borderLeft: 4, borderLeftColor: workspace.execution_readiness.ready ? "success.main" : "divider" }}><Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={1.5}><Box><Typography variant="h6">执行准备状态</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{workspace.execution_readiness.message}</Typography></Box><Chip label={workspace.execution_readiness.ready ? "可进入执行准备" : workspace.execution_readiness.state === "draft" ? "等待人工批准" : "尚未生成计划"} color={workspace.execution_readiness.ready ? "success" : "default"} variant={workspace.execution_readiness.ready ? "filled" : "outlined"} /></Stack>{workspace.execution_readiness.steps.length > 0 && <Stack spacing={0.75} sx={{ mt: 1.5 }}>{workspace.execution_readiness.steps.map((step) => <Typography variant="body2" key={step.id}>• {step.id}：{step.objective}</Typography>)}</Stack>}</Paper>
    <Paper variant="outlined" sx={{ p: { xs: 2.25, md: 3 } }}><Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={1}><Box><Typography variant="h5">4. 多假设实验矩阵</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>同一任务不再只押注一种解释。每个候选机制都给出控制变量、历史支持和失败后的切换路线。</Typography></Box><Chip label={workspace.hypothesis_matrix.method} variant="outlined" /></Stack><Grid container spacing={2} sx={{ mt: 1 }}>{workspace.hypothesis_matrix.hypotheses.map((item) => <Grid key={item.id} size={{ xs: 12, lg: 4 }}><Paper variant="outlined" sx={{ p: 2, height: "100%" }}><Stack direction="row" justifyContent="space-between" gap={1}><Typography variant="subtitle1" fontWeight={700}>{item.mechanism}</Typography><Chip size="small" label={item.priority === "high" ? "优先验证" : "备选"} color={item.priority === "high" ? "primary" : "default"} variant={item.priority === "high" ? "filled" : "outlined"} /></Stack><Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>{item.statement}</Typography><Divider sx={{ my: 1.25 }} /><Typography variant="caption" color="text.secondary">控制变量</Typography>{Object.entries(item.variables).map(([key, value]) => <Typography variant="body2" key={key}>{key}：{value}</Typography>)}<Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.25 }}>历史支持</Typography><Typography variant="body2">正例 {item.historical_support.relation_counts.confirmed ?? 0} · 观察 {item.historical_support.relation_counts.observed ?? 0} · 负例 {item.historical_support.relation_counts.negative ?? 0}</Typography><Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.25 }}>若未支持此假设</Typography><Typography variant="body2">转向：{item.next_if_negative}</Typography></Paper></Grid>)}</Grid></Paper>
    <Paper variant="outlined" sx={{ p: { xs: 2.25, md: 3 } }}><Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={1}><Box><Typography variant="h5">5. 记录一轮观察</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>把你手动发送的内容、模型响应和外部可观察结果放进同一条记录。记录后，系统会更新下一步建议。</Typography></Box><StatusChip value={task.stage} /></Stack><Grid container spacing={2} sx={{ mt: 1 }}><Grid size={{ xs: 12, md: 6 }}><TextField label="本轮输入（可选）" value={inputText} onChange={(event) => setInputText(event.target.value)} multiline minRows={4} fullWidth /></Grid><Grid size={{ xs: 12, md: 6 }}><TextField label="观察到的响应（必填）" value={responseText} onChange={(event) => setResponseText(event.target.value)} multiline minRows={4} fullWidth /></Grid><Grid size={{ xs: 12, md: 4 }}><TextField label="本轮机制" value={mechanism} onChange={(event) => setMechanism(event.target.value)} fullWidth helperText="记录正在验证的机制，而不是某个具体输入。" /></Grid><Grid size={{ xs: 12, md: 4 }}><TextField label="结果标签" value={outcome} onChange={(event) => setOutcome(event.target.value)} fullWidth helperText="例如 unknown、refused、no_change。" /></Grid><Grid size={{ xs: 12, md: 4 }}><TextField label="外部可观察效果" value={effect} onChange={(event) => setEffect(event.target.value)} fullWidth helperText="例如平台状态、工具结果或无变化。" /></Grid><Grid size={{ xs: 12, md: 8 }}><TextField label="证据说明（可选）" value={evidenceDescription} onChange={(event) => setEvidenceDescription(event.target.value)} fullWidth helperText="只有平台、工具、UI 或人工核验支持的事实才应标为已验证。" /></Grid><Grid size={{ xs: 12, md: 4 }}><Stack direction="row" alignItems="center" height="100%" flexWrap="wrap"><FormControlLabel control={<Checkbox checked={refusal} onChange={(event) => setRefusal(event.target.checked)} />} label="本轮出现拒绝" /><FormControlLabel control={<Checkbox checked={evidenceVerified} onChange={(event) => setEvidenceVerified(event.target.checked)} />} label="证据已核验" /></Stack></Grid></Grid><Button variant="contained" disabled={saving} onClick={() => void saveObservation()} sx={{ mt: 2 }}>保存观察并更新下一步</Button></Paper>
  </Stack>;
}

function DetailPage({ detail, close }: { detail: CaseDetail; close: () => void }) {
  const [tab, setTab] = useState(0);
  const [mechanism, reuse] = experienceFrom(detail);
  const sections = [
    <Stack spacing={2} key="overview"><Typography variant="h5">{detail.title}</Typography><Stack direction="row" spacing={1}><StatusChip value={detail.status} /><Chip size="small" label={mechanism} variant="outlined" /></Stack><Typography color="text.secondary">{detail.challenge || "尚未记录题目内容。"}</Typography><Divider /><Typography variant="subtitle2">从这个案例可以复用什么</Typography><Typography>{reuse}</Typography><Typography variant="subtitle2">你的原始复盘</Typography><Typography color="text.secondary" sx={{ whiteSpace: "pre-wrap" }}>{detail.notes || "尚未整理复盘。"}</Typography></Stack>,
    <Stack spacing={1} key="evidence">{detail.evidence.length ? detail.evidence.map((item) => <Paper key={item.evidence_id} variant="outlined" sx={{ p: 1.5 }}><Stack direction="row" justifyContent="space-between" gap={1}><Typography>{item.description}</Typography><StatusChip value={item.verified ? "verified" : "unverified"} /></Stack><Typography variant="caption" color="text.secondary">{item.kind} · {item.source}</Typography></Paper>) : <Typography color="text.secondary">尚无证据记录。执行后的响应、截图或平台判据可在这里形成证据链。</Typography>}</Stack>,
    <Stack spacing={1} key="plans">{detail.plans.length ? detail.plans.map((item) => <Paper key={item.plan_id} variant="outlined" sx={{ p: 1.5 }}><Stack direction="row" justifyContent="space-between"><Typography>{item.planner}</Typography><StatusChip value={item.status} /></Stack><Typography variant="caption" color="text.secondary">{item.steps.length} 个计划步骤</Typography></Paper>) : <Typography color="text.secondary">尚无计划记录。导入新关卡后可先生成并审核测试计划。</Typography>}</Stack>,
    <Stack spacing={1} key="campaigns">{detail.campaigns.length ? detail.campaigns.map((item) => <Paper key={item.campaign_id} variant="outlined" sx={{ p: 1.5 }}><Stack direction="row" justifyContent="space-between"><Typography>{item.target_kind}</Typography><StatusChip value={item.status} /></Stack><Typography variant="caption" color="text.secondary">已执行 {item.executed_turns} 轮 · {item.stop_reason}</Typography></Paper>) : <Typography color="text.secondary">尚无执行记录。批准计划并设置预算后，才会进入 Campaign。</Typography>}</Stack>,
  ];
  return <Stack spacing={2.5}><Button startIcon={<ArrowBackRoundedIcon />} onClick={close} sx={{ alignSelf: "flex-start" }}>返回上一页</Button><Box><Typography variant="overline" color="primary.main">案例工作区</Typography><Typography variant="h4">{detail.title}</Typography></Box><Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable"><Tab label="概览与复盘" /><Tab label={`证据 (${detail.evidence.length})`} /><Tab label={`计划 (${detail.plans.length})`} /><Tab label={`执行 (${detail.campaigns.length})`} /></Tabs><Paper variant="outlined" sx={{ p: { xs: 2, md: 3 } }}>{sections[tab]}</Paper></Stack>;
}

function App() {
  const [page, setPage] = useState<Page>("home");
  const [source, setSource] = useState("user-kb");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [research, setResearch] = useState<ResearchSummary | null>(null);
  const [paperPacket, setPaperPacket] = useState<PaperPacket | null>(null);
  const [workspace, setWorkspace] = useState<TaskWorkspace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [newTask, setNewTask] = useState({ title: "", target: "", challenge: "", successCriteria: "", authorization: "" });
  const [creatingTask, setCreatingTask] = useState(false);
  const load = async (nextSource = source) => { try { setError(null); const [nextOverview, nextCases, nextResearch, nextPacket] = await Promise.all([api.overview(nextSource), api.cases(nextSource), api.research(nextSource), api.paperPacket(nextSource)]); setOverview(nextOverview); setCases(nextCases); setResearch(nextResearch); setPaperPacket(nextPacket); } catch (err) { setError(err instanceof Error ? err.message : "无法连接本地 API"); } };
  useEffect(() => { void load(source); }, [source]);
  const selectCase = async (caseId: string) => { try { setWorkspace(await api.taskWorkspace(caseId)); } catch (err) { setError(err instanceof Error ? err.message : "无法加载任务"); } };
  const submitTask = async () => { if (!newTask.title.trim()) { setError("请至少填写任务名称。"); return; } setCreatingTask(true); try { const result = await api.createTask({ title: newTask.title, target: newTask.target, challenge: newTask.challenge, authorization_scope: newTask.authorization, success_criteria: newTask.successCriteria.split("\n").map((item) => item.trim()).filter(Boolean) }); setIntakeOpen(false); setNewTask({ title: "", target: "", challenge: "", successCriteria: "", authorization: "" }); await load(); await selectCase(result.case_id); } catch (err) { setError(err instanceof Error ? err.message : "创建任务失败"); } finally { setCreatingTask(false); } };
  const go = (next: Page) => { setWorkspace(null); setPage(next); };
  const nav = useMemo(() => [
    ["home", "首页", <DashboardRoundedIcon />], ["cases", "我的案例", <FolderOpenRoundedIcon />], ["experience", "我的经验", <MenuBookRoundedIcon />], ["research", "研究分析", <ScienceRoundedIcon />],
  ] as const, []);
  return <ThemeProvider theme={theme}><CssBaseline /><Box sx={{ display: "flex", minHeight: "100vh" }}>
    <AppBar position="fixed" elevation={0} sx={{ zIndex: (value) => value.zIndex.drawer + 1, borderBottom: 1, borderColor: "divider", backgroundColor: "background.default" }}><Toolbar sx={{ minHeight: { xs: 64, md: 72 } }}><HubRoundedIcon sx={{ mr: 1.25, color: "primary.main" }} /><Typography variant="h6" sx={{ flexGrow: 1 }}>LLM 红队助手</Typography><ToggleButtonGroup size="small" value={source} exclusive onChange={(_, value) => { if (value) { setSource(value); setWorkspace(null); } }} sx={{ mr: 1.5 }}><ToggleButton value="user-kb">我的知识库</ToggleButton><ToggleButton value="all">全部数据</ToggleButton></ToggleButtonGroup><Button color="inherit" onClick={() => void load()}>刷新</Button></Toolbar></AppBar>
    <Drawer variant="permanent" sx={{ width: drawerWidth, flexShrink: 0, "& .MuiDrawer-paper": { width: drawerWidth, boxSizing: "border-box", borderRight: 1, borderColor: "divider", backgroundImage: "none" } }}><Toolbar sx={{ minHeight: { xs: 64, md: 72 } }} /><List sx={{ px: 1.25, pt: 2 }}>{nav.map(([key, label, icon]) => <ListItemButton key={key} selected={page === key && !workspace} onClick={() => go(key)} sx={{ borderRadius: 1.5, mb: 0.5 }}><ListItemIcon>{icon}</ListItemIcon><ListItemText primary={label} /></ListItemButton>)}</List><Divider sx={{ mx: 2, my: 1 }} /><Box sx={{ px: 2.5, py: 2 }}><Stack direction="row" spacing={1} alignItems="center"><FactCheckRoundedIcon color="primary" fontSize="small" /><Typography variant="body2" fontWeight={600}>本地优先</Typography></Stack><Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>你的案例和证据保存在本机。这里不会自动把公开种子算作个人成绩。</Typography></Box></Drawer>
    <Box component="main" sx={{ flexGrow: 1, p: { xs: 2, md: 4 }, pt: { xs: 11, md: 13 }, maxWidth: 1560, width: "100%" }}>{error && <Alert severity="error" sx={{ mb: 2 }}>{error}。请先运行 <code>python -m redteam_memory serve</code>。</Alert>}{!overview || !research || !paperPacket ? <Box sx={{ display: "grid", placeItems: "center", minHeight: 320 }}><CircularProgress /></Box> : workspace ? <TaskWorkspacePage workspace={workspace} close={() => setWorkspace(null)} refresh={async () => { await load(); setWorkspace(await api.taskWorkspace(workspace.task.case_id)); }} /> : page === "home" ? <HomePage overview={overview} rows={cases} selectCase={selectCase} goToCases={() => go("cases")} goToExperience={() => go("experience")} openIntake={() => setIntakeOpen(true)} /> : page === "cases" ? <CasesPage rows={cases} selectCase={selectCase} /> : page === "experience" ? <ExperiencePage rows={cases} goToCases={() => go("cases")} /> : <ResearchPage summary={research} packet={paperPacket} />}</Box>
    <Dialog open={intakeOpen} onClose={() => setIntakeOpen(false)} maxWidth="md" fullWidth><DialogTitle>开始一个新任务</DialogTitle><DialogContent dividers><Stack spacing={2}><Typography color="text.secondary">先记录你已经知道的事实。创建后会直接进入任务控制台，由机制匹配和实验草稿帮助你推进。</Typography><TextField autoFocus required label="任务名称" value={newTask.title} onChange={(event) => setNewTask({ ...newTask, title: event.target.value })} fullWidth placeholder="例如：某关卡的会话状态研究" /><TextField label="目标 / 模型" value={newTask.target} onChange={(event) => setNewTask({ ...newTask, target: event.target.value })} fullWidth placeholder="例如：关卡名称、模型或本地沙箱" /><TextField label="题目与当前已知上下文" value={newTask.challenge} onChange={(event) => setNewTask({ ...newTask, challenge: event.target.value })} multiline minRows={4} fullWidth /><TextField label="成功判据（每行一条）" value={newTask.successCriteria} onChange={(event) => setNewTask({ ...newTask, successCriteria: event.target.value })} multiline minRows={3} fullWidth /><TextField label="授权范围与约束" value={newTask.authorization} onChange={(event) => setNewTask({ ...newTask, authorization: event.target.value })} multiline minRows={2} fullWidth /></Stack></DialogContent><DialogActions><Button onClick={() => setIntakeOpen(false)}>取消</Button><Button variant="contained" disabled={creatingTask} onClick={() => void submitTask()}>创建并进入任务</Button></DialogActions></Dialog>
  </Box></ThemeProvider>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
