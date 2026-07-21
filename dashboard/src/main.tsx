import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Alert, AppBar, Box, Button, Chip, CircularProgress, CssBaseline, Dialog,
  DialogActions, DialogContent, DialogTitle, Divider, Drawer, Grid, List,
  ListItemButton, ListItemIcon, ListItemText, Paper, Stack, Tab, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, Tabs, Toolbar,
  ToggleButton, ToggleButtonGroup, Typography, ThemeProvider,
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
import type { CaseDetail, CaseRow, Overview, PaperPacket, ResearchSummary } from "./types";

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

function CaseCard({ row, onOpen }: { row: CaseRow; onOpen: () => void }) {
  const [mechanism, reuse] = experienceFrom(row);
  return <Paper variant="outlined" sx={{ p: 2.25, height: "100%", display: "flex", flexDirection: "column" }}>
    <Stack direction="row" justifyContent="space-between" gap={1} alignItems="flex-start">
      <Box sx={{ minWidth: 0 }}><Typography variant="subtitle1" fontWeight={600} noWrap title={row.title}>{row.title}</Typography><Typography variant="caption" color="text.secondary">{row.target || "目标未记录"}</Typography></Box>
      <StatusChip value={row.status} />
    </Stack>
    <Divider sx={{ my: 1.75 }} />
    <Typography variant="caption" color="text.secondary">可复用机制</Typography>
    <Typography variant="body2" sx={{ mt: 0.35, fontWeight: 600 }}>{mechanism}</Typography>
    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.65, mb: 2, flexGrow: 1 }}>{reuse}</Typography>
    <Button size="small" onClick={onOpen} sx={{ alignSelf: "flex-start" }}>查看复盘</Button>
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

    <Box>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "center" }} gap={1} sx={{ mb: 2 }}>
        <Box><Typography variant="h5">我的已通关经验</Typography><Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>先展示你的历史记录；每一条都可以回到原始复盘，而不是只留下一个分数。</Typography></Box>
        <Button onClick={goToExperience}>查看全部经验</Button>
      </Stack>
      {confirmed.length ? <Grid container spacing={2.25}>{confirmed.slice(0, 6).map((row) => <Grid key={row.case_id} size={{ xs: 12, md: 6, xl: 4 }}><CaseCard row={row} onOpen={() => selectCase(row.case_id)} /></Grid>)}</Grid> : <EmptyState title="还没有历史通关记录" description="把你已有的通关复盘导入后，这里会自动成为你的个人经验库。" action="查看我的案例" onAction={goToCases} />}
    </Box>
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

function ExperiencePage({ rows, selectCase }: { rows: CaseRow[]; selectCase: (id: string) => void }) {
  const confirmed = rows.filter((row) => row.status === "confirmed");
  return <Stack spacing={3}>
    <Box><Typography variant="h4">我的经验库</Typography><Typography color="text.secondary" sx={{ mt: 0.75 }}>把历史通关变成可复用的机制。每个卡片先说“学到什么”，再回到原始案例核对事实。</Typography></Box>
    {confirmed.length ? <Grid container spacing={2.25}>{confirmed.map((row) => <Grid key={row.case_id} size={{ xs: 12, md: 6, xl: 4 }}><CaseCard row={row} onOpen={() => selectCase(row.case_id)} /></Grid>)}</Grid> : <EmptyState title="经验库还在等待第一条记录" description="导入或整理一个已完成案例后，它会出现在这里。" action="查看我的案例" onAction={() => undefined} />}
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
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [intakeOpen, setIntakeOpen] = useState(false);
  const load = async (nextSource = source) => { try { setError(null); const [nextOverview, nextCases, nextResearch, nextPacket] = await Promise.all([api.overview(nextSource), api.cases(nextSource), api.research(nextSource), api.paperPacket(nextSource)]); setOverview(nextOverview); setCases(nextCases); setResearch(nextResearch); setPaperPacket(nextPacket); } catch (err) { setError(err instanceof Error ? err.message : "无法连接本地 API"); } };
  useEffect(() => { void load(source); }, [source]);
  const selectCase = async (caseId: string) => { try { setDetail(await api.caseDetail(caseId)); } catch (err) { setError(err instanceof Error ? err.message : "无法加载案例"); } };
  const go = (next: Page) => { setDetail(null); setPage(next); };
  const nav = useMemo(() => [
    ["home", "首页", <DashboardRoundedIcon />], ["cases", "我的案例", <FolderOpenRoundedIcon />], ["experience", "我的经验", <MenuBookRoundedIcon />], ["research", "研究分析", <ScienceRoundedIcon />],
  ] as const, []);
  return <ThemeProvider theme={theme}><CssBaseline /><Box sx={{ display: "flex", minHeight: "100vh" }}>
    <AppBar position="fixed" elevation={0} sx={{ zIndex: (value) => value.zIndex.drawer + 1, borderBottom: 1, borderColor: "divider", backgroundColor: "background.default" }}><Toolbar sx={{ minHeight: { xs: 64, md: 72 } }}><HubRoundedIcon sx={{ mr: 1.25, color: "primary.main" }} /><Typography variant="h6" sx={{ flexGrow: 1 }}>LLM 红队助手</Typography><ToggleButtonGroup size="small" value={source} exclusive onChange={(_, value) => { if (value) { setSource(value); setDetail(null); } }} sx={{ mr: 1.5 }}><ToggleButton value="user-kb">我的知识库</ToggleButton><ToggleButton value="all">全部数据</ToggleButton></ToggleButtonGroup><Button color="inherit" onClick={() => void load()}>刷新</Button></Toolbar></AppBar>
    <Drawer variant="permanent" sx={{ width: drawerWidth, flexShrink: 0, "& .MuiDrawer-paper": { width: drawerWidth, boxSizing: "border-box", borderRight: 1, borderColor: "divider", backgroundImage: "none" } }}><Toolbar sx={{ minHeight: { xs: 64, md: 72 } }} /><List sx={{ px: 1.25, pt: 2 }}>{nav.map(([key, label, icon]) => <ListItemButton key={key} selected={page === key && !detail} onClick={() => go(key)} sx={{ borderRadius: 1.5, mb: 0.5 }}><ListItemIcon>{icon}</ListItemIcon><ListItemText primary={label} /></ListItemButton>)}</List><Divider sx={{ mx: 2, my: 1 }} /><Box sx={{ px: 2.5, py: 2 }}><Stack direction="row" spacing={1} alignItems="center"><FactCheckRoundedIcon color="primary" fontSize="small" /><Typography variant="body2" fontWeight={600}>本地优先</Typography></Stack><Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>你的案例和证据保存在本机。这里不会自动把公开种子算作个人成绩。</Typography></Box></Drawer>
    <Box component="main" sx={{ flexGrow: 1, p: { xs: 2, md: 4 }, pt: { xs: 11, md: 13 }, maxWidth: 1560, width: "100%" }}>{error && <Alert severity="error" sx={{ mb: 2 }}>{error}。请先运行 <code>python -m redteam_memory serve</code>。</Alert>}{!overview || !research || !paperPacket ? <Box sx={{ display: "grid", placeItems: "center", minHeight: 320 }}><CircularProgress /></Box> : detail ? <DetailPage detail={detail} close={() => setDetail(null)} /> : page === "home" ? <HomePage overview={overview} rows={cases} selectCase={selectCase} goToCases={() => go("cases")} goToExperience={() => go("experience")} openIntake={() => setIntakeOpen(true)} /> : page === "cases" ? <CasesPage rows={cases} selectCase={selectCase} /> : page === "experience" ? <ExperiencePage rows={cases} selectCase={selectCase} /> : <ResearchPage summary={research} packet={paperPacket} />}</Box>
    <Dialog open={intakeOpen} onClose={() => setIntakeOpen(false)} maxWidth="sm" fullWidth><DialogTitle>导入一个新关卡</DialogTitle><DialogContent dividers><Stack spacing={2}><Typography>第一版采用结构化 JSON 导入，目的是保留题目、授权范围、成功判据和已有对话，避免以后只能靠截图回忆上下文。</Typography><Paper variant="outlined" sx={{ p: 1.5, backgroundColor: "background.default" }}><Typography component="code" variant="body2">python -m redteam_memory intake import examples/challenge-intake.example.json</Typography></Paper><Typography variant="body2" color="text.secondary">可先复制 <code>examples/challenge-intake.example.json</code>，把题目内容和授权范围填进去。导入后在“我的案例”中打开它，再匹配历史经验、创建计划并记录响应。</Typography></Stack></DialogContent><DialogActions><Button onClick={() => setIntakeOpen(false)}>知道了</Button><Button variant="contained" onClick={() => { setIntakeOpen(false); go("cases"); }}>打开我的案例</Button></DialogActions></Dialog>
  </Box></ThemeProvider>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
