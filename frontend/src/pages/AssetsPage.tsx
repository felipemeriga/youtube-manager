import { useState, useEffect, useCallback, useRef } from "react";
import {
  Box,
  Typography,
  Tabs,
  Tab,
  Snackbar,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Button,
  Collapse,
  LinearProgress,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadIcon from "@mui/icons-material/Download";
import ClearIcon from "@mui/icons-material/Clear";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import AssetGrid from "../components/AssetGrid";
import AssetUpload from "../components/AssetUpload";
import ScriptViewer from "../components/ScriptViewer";
import type { FileUploadItem } from "../components/AssetUpload";
import {
  listAssets,
  uploadAsset,
  deleteAsset,
  fetchAssetText,
  reindexPhotos,
} from "../lib/api";

const BUCKETS = [
  { key: "reference-thumbs", label: "Thumbnails de Referência", accept: "image/*" },
  { key: "personal-photos", label: "Fotos Pessoais", accept: "image/*" },
  { key: "logos", label: "Logos", accept: "image/*" },
  { key: "outputs", label: "Resultados Gerados", accept: "image/*" },
  { key: "scripts", label: "Roteiros", accept: ".md" },
  { key: "fonts", label: "Fontes", accept: ".ttf,.otf,.woff" },
];

interface AssetFile {
  name: string;
  public_url?: string;
  metadata?: { size?: number };
}

type BatchItemStatus = "pending" | "done" | "error";

interface BatchItem {
  name: string;
  status: BatchItemStatus;
}

interface BatchProgress {
  type: "download" | "delete";
  items: BatchItem[];
  collapsed: boolean;
  done: boolean;
}

// ---------------------------------------------------------------------------
// SelectionToolbar
// ---------------------------------------------------------------------------
function SelectionToolbar({
  count,
  onDownload,
  onDelete,
  onClear,
}: {
  count: number;
  onDownload: () => void;
  onDelete: () => void;
  onClear: () => void;
}) {
  if (count === 0) return null;

  return (
    <Box
      sx={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 1300,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 2,
        py: 1.5,
        px: 3,
        backgroundColor: "rgba(15,15,25,0.85)",
        backdropFilter: "blur(12px)",
        borderTop: "1px solid rgba(124,58,237,0.3)",
      }}
    >
      <Typography variant="body2" sx={{ color: "#a78bfa", fontWeight: 600, mr: 1 }}>
        {count} selecionado{count > 1 ? "s" : ""}
      </Typography>
      <Button
        size="small"
        variant="outlined"
        startIcon={<DownloadIcon />}
        onClick={onDownload}
        sx={{
          borderColor: "rgba(124,58,237,0.4)",
          color: "#a78bfa",
          textTransform: "none",
          "&:hover": {
            borderColor: "#7c3aed",
            backgroundColor: "rgba(124,58,237,0.1)",
          },
        }}
      >
        Baixar selecionados
      </Button>
      <Button
        size="small"
        variant="outlined"
        startIcon={<DeleteOutlineIcon />}
        onClick={onDelete}
        sx={{
          borderColor: "rgba(239,68,68,0.4)",
          color: "#ef4444",
          textTransform: "none",
          "&:hover": {
            borderColor: "#ef4444",
            backgroundColor: "rgba(239,68,68,0.1)",
          },
        }}
      >
        Excluir selecionados
      </Button>
      <Button
        size="small"
        variant="text"
        startIcon={<ClearIcon />}
        onClick={onClear}
        sx={{
          color: "rgba(255,255,255,0.5)",
          textTransform: "none",
          "&:hover": { color: "rgba(255,255,255,0.8)" },
        }}
      >
        Limpar seleção
      </Button>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// BatchProgressDialog
// ---------------------------------------------------------------------------
function BatchProgressDialog({
  progress,
  onToggleCollapse,
  onDismiss,
}: {
  progress: BatchProgress | null;
  onToggleCollapse: () => void;
  onDismiss: () => void;
}) {
  if (!progress) return null;

  const completed = progress.items.filter((i) => i.status !== "pending").length;
  const total = progress.items.length;
  const pct = total > 0 ? (completed / total) * 100 : 0;
  const label = progress.type === "download" ? "Download" : "Exclusão";

  const statusIcon = (status: BatchItemStatus) => {
    if (status === "done")
      return <CheckCircleIcon sx={{ fontSize: 16, color: "#10b981" }} />;
    if (status === "error")
      return <ErrorIcon sx={{ fontSize: 16, color: "#ef4444" }} />;
    return <HourglassEmptyIcon sx={{ fontSize: 16, color: "rgba(255,255,255,0.3)" }} />;
  };

  return (
    <Box
      sx={{
        position: "fixed",
        bottom: 60,
        right: 20,
        zIndex: 1400,
        width: 320,
        backgroundColor: "rgba(20,20,30,0.95)",
        backdropFilter: "blur(16px)",
        border: "1px solid rgba(124,58,237,0.3)",
        borderRadius: 2,
        overflow: "hidden",
        boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
      }}
    >
      {/* Header */}
      <Box
        onClick={onToggleCollapse}
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 2,
          py: 1.5,
          cursor: "pointer",
          "&:hover": { backgroundColor: "rgba(255,255,255,0.03)" },
        }}
      >
        <Box>
          <Typography variant="body2" sx={{ color: "#a78bfa", fontWeight: 600 }}>
            {label}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {completed}/{total} concluídos
          </Typography>
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          {progress.done && (
            <IconButton size="small" onClick={(e) => { e.stopPropagation(); onDismiss(); }}>
              <CloseIcon sx={{ fontSize: 16, color: "rgba(255,255,255,0.4)" }} />
            </IconButton>
          )}
          {progress.collapsed ? (
            <ExpandLessIcon sx={{ color: "rgba(255,255,255,0.4)", fontSize: 20 }} />
          ) : (
            <ExpandMoreIcon sx={{ color: "rgba(255,255,255,0.4)", fontSize: 20 }} />
          )}
        </Box>
      </Box>

      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          height: 2,
          backgroundColor: "rgba(124,58,237,0.1)",
          "& .MuiLinearProgress-bar": {
            backgroundColor: progress.done ? "#10b981" : "#7c3aed",
          },
        }}
      />

      {/* Collapsible item list */}
      <Collapse in={!progress.collapsed}>
        <Box sx={{ maxHeight: 200, overflow: "auto", px: 2, py: 1 }}>
          {progress.items.map((item) => (
            <Box
              key={item.name}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                py: 0.5,
              }}
            >
              {statusIcon(item.status)}
              <Typography
                variant="caption"
                sx={{
                  color:
                    item.status === "done"
                      ? "rgba(255,255,255,0.5)"
                      : item.status === "error"
                      ? "#ef4444"
                      : "rgba(255,255,255,0.7)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {item.name}
              </Typography>
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// AssetsPage
// ---------------------------------------------------------------------------
export default function AssetsPage() {
  const [activeTab, setActiveTab] = useState(0);
  const [files, setFiles] = useState<AssetFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [fileStatuses, setFileStatuses] = useState<FileUploadItem[]>([]);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({ open: false, message: "", severity: "success" });
  const [reindexing, setReindexing] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerContent, setViewerContent] = useState("");
  const [viewerTitle, setViewerTitle] = useState("");

  // Multi-select state
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
  const autoDismissRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const currentBucket = BUCKETS[activeTab];

  const loadFiles = useCallback(async () => {
    setLoading(true);
    const data = await listAssets(currentBucket.key);
    setFiles(data as unknown as AssetFile[]);
    setLoading(false);
  }, [currentBucket.key]);

  useEffect(() => {
    loadFiles();
  }, [loadFiles]);

  // Clear selection when switching tabs
  useEffect(() => {
    setSelected(new Set());
  }, [activeTab]);

  // ---------- Selection handlers ----------

  const handleToggleSelect = useCallback((name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelected((prev) => {
      const allSelected = files.length > 0 && files.every((f) => prev.has(f.name));
      if (allSelected) {
        return new Set();
      }
      return new Set(files.map((f) => f.name));
    });
  }, [files]);

  const clearSelection = useCallback(() => setSelected(new Set()), []);

  // ---------- Batch operations ----------

  const handleBatchDelete = useCallback(async () => {
    const names = Array.from(selected);
    if (names.length === 0) return;

    const items: BatchItem[] = names.map((n) => ({ name: n, status: "pending" as const }));
    setBatchProgress({ type: "delete", items, collapsed: false, done: false });

    for (let i = 0; i < names.length; i++) {
      try {
        await deleteAsset(currentBucket.key, names[i]);
        setBatchProgress((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((item, idx) =>
                  idx === i ? { ...item, status: "done" } : item
                ),
              }
            : prev
        );
      } catch {
        setBatchProgress((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((item, idx) =>
                  idx === i ? { ...item, status: "error" } : item
                ),
              }
            : prev
        );
      }
    }

    setBatchProgress((prev) => (prev ? { ...prev, done: true } : prev));
    setSelected(new Set());
    loadFiles();

    autoDismissRef.current = setTimeout(() => setBatchProgress(null), 5000);
  }, [selected, currentBucket.key, loadFiles]);

  const handleBatchDownload = useCallback(async () => {
    const names = Array.from(selected);
    if (names.length === 0) return;

    const items: BatchItem[] = names.map((n) => ({ name: n, status: "pending" as const }));
    setBatchProgress({ type: "download", items, collapsed: false, done: false });

    for (let i = 0; i < names.length; i++) {
      try {
        const file = files.find((f) => f.name === names[i]);
        const url =
          file?.public_url || `/api/assets/${currentBucket.key}/${names[i]}`;
        window.open(url, "_blank");
        // Small delay between downloads to avoid popup blocking
        await new Promise((r) => setTimeout(r, 400));
        setBatchProgress((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((item, idx) =>
                  idx === i ? { ...item, status: "done" } : item
                ),
              }
            : prev
        );
      } catch {
        setBatchProgress((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((item, idx) =>
                  idx === i ? { ...item, status: "error" } : item
                ),
              }
            : prev
        );
      }
    }

    setBatchProgress((prev) => (prev ? { ...prev, done: true } : prev));

    autoDismissRef.current = setTimeout(() => setBatchProgress(null), 5000);
  }, [selected, files, currentBucket.key]);

  const toggleBatchCollapse = useCallback(() => {
    setBatchProgress((prev) =>
      prev ? { ...prev, collapsed: !prev.collapsed } : prev
    );
  }, []);

  const dismissBatch = useCallback(() => {
    if (autoDismissRef.current) clearTimeout(autoDismissRef.current);
    setBatchProgress(null);
  }, []);

  // ---------- File operations ----------

  const handleUpload = async (fileList: FileList) => {
    const items: FileUploadItem[] = Array.from(fileList).map((f) => ({
      name: f.name,
      status: "pending" as const,
    }));
    setFileStatuses(items);

    let succeeded = 0;
    let failed = 0;

    for (let i = 0; i < fileList.length; i++) {
      setFileStatuses((prev) =>
        prev.map((item, idx) =>
          idx === i ? { ...item, status: "uploading" } : item
        )
      );

      try {
        await uploadAsset(currentBucket.key, fileList[i]);
        succeeded++;
        setFileStatuses((prev) =>
          prev.map((item, idx) =>
            idx === i ? { ...item, status: "done" } : item
          )
        );
      } catch {
        failed++;
        setFileStatuses((prev) =>
          prev.map((item, idx) =>
            idx === i ? { ...item, status: "error" } : item
          )
        );
      }
    }

    loadFiles();

    if (failed > 0) {
      setSnackbar({
        open: true,
        message: `Enviado(s) ${succeeded} arquivo(s). ${failed} falharam.`,
        severity: "error",
      });
    } else {
      setSnackbar({
        open: true,
        message: `${succeeded} arquivo(s) enviado(s) com sucesso`,
        severity: "success",
      });
    }

    setTimeout(() => setFileStatuses([]), 3000);
  };

  const handleDelete = async (name: string) => {
    await deleteAsset(currentBucket.key, name);
    loadFiles();
    setSnackbar({
      open: true,
      message: `${name} excluído`,
      severity: "success",
    });
  };

  const handleDownload = (name: string) => {
    const file = files.find((f) => f.name === name);
    const url = file?.public_url || `/api/assets/${currentBucket.key}/${name}`;
    window.open(url, "_blank");
  };

  const handleReindex = async () => {
    setReindexing(true);
    try {
      const result = await reindexPhotos();
      setSnackbar({
        open: true,
        message: `Indexou ${result.indexed} novas fotos (${result.skipped} já indexadas, ${result.total} total)`,
        severity: "success",
      });
    } catch (err) {
      const detail = err instanceof Error ? err.message : "";
      setSnackbar({
        open: true,
        message: detail
          ? `Falha ao indexar fotos: ${detail}`
          : "Falha ao indexar fotos",
        severity: "error",
      });
    } finally {
      setReindexing(false);
    }
  };

  const handleViewScript = async (name: string) => {
    try {
      const content = await fetchAssetText(currentBucket.key, name);
      setViewerTitle(
        name
          .replace(/\.md$/, "")
          .replace(/-\d{8}-\d{6}$/, "")
          .replace(/-/g, " ")
          .replace(/\b\w/g, (c) => c.toUpperCase())
      );
      setViewerContent(content);
      setViewerOpen(true);
    } catch (err) {
      const detail = err instanceof Error ? err.message : "";
      setSnackbar({
        open: true,
        message: detail
          ? `Falha ao carregar roteiro: ${detail}`
          : "Falha ao carregar roteiro",
        severity: "error",
      });
    }
  };

  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        p: 3,
        overflow: "auto",
        // Extra bottom padding when toolbar is visible
        pb: selected.size > 0 ? 10 : 3,
      }}
    >
      <Typography
        variant="h5"
        sx={{
          mb: 2,
          background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}
      >
        Arquivos
      </Typography>

      <Tabs
        value={activeTab}
        onChange={(_, v) => setActiveTab(v)}
        sx={{
          mb: 3,
          "& .MuiTab-root": { textTransform: "none" },
          "& .Mui-selected": { color: "#7c3aed" },
          "& .MuiTabs-indicator": { backgroundColor: "#7c3aed" },
        }}
      >
        {BUCKETS.map((b) => (
          <Tab key={b.key} label={b.label} />
        ))}
      </Tabs>

      {currentBucket.key !== "outputs" && currentBucket.key !== "scripts" && (
        <Box sx={{ mb: 3 }}>
          <AssetUpload
            onUpload={handleUpload}
            accept={currentBucket.accept}
            fileStatuses={fileStatuses}
          />
          {currentBucket.key === "personal-photos" && (
            <Box sx={{ mt: 1.5 }}>
              <Button
                variant="outlined"
                startIcon={<AutoFixHighIcon />}
                onClick={handleReindex}
                disabled={reindexing}
                size="small"
                sx={{
                  borderColor: "rgba(124,58,237,0.3)",
                  color: "#a78bfa",
                  whiteSpace: "nowrap",
                  "&:hover": {
                    borderColor: "#7c3aed",
                    backgroundColor: "rgba(124,58,237,0.08)",
                  },
                }}
              >
                {reindexing ? "Indexando..." : "Indexar Fotos"}
              </Button>
            </Box>
          )}
        </Box>
      )}

      {loading ? (
        <Typography color="text.secondary">Carregando...</Typography>
      ) : (
        <AssetGrid
          files={files}
          bucket={currentBucket.key}
          onDelete={handleDelete}
          onDownload={handleDownload}
          onView={
            currentBucket.key === "scripts" ? handleViewScript : undefined
          }
          selected={selected}
          onToggleSelect={handleToggleSelect}
          onSelectAll={handleSelectAll}
        />
      )}

      {/* Selection toolbar */}
      <SelectionToolbar
        count={selected.size}
        onDownload={handleBatchDownload}
        onDelete={handleBatchDelete}
        onClear={clearSelection}
      />

      {/* Batch progress dialog */}
      <BatchProgressDialog
        progress={batchProgress}
        onToggleCollapse={toggleBatchCollapse}
        onDismiss={dismissBatch}
      />

      <Dialog
        open={viewerOpen}
        onClose={() => setViewerOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: {
            backgroundColor: "rgba(20,20,30,0.98)",
            backdropFilter: "blur(20px)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 3,
            maxHeight: "85vh",
          },
        }}
      >
        <DialogTitle
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            pb: 1,
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {viewerTitle}
          </Typography>
          <IconButton
            onClick={() => setViewerOpen(false)}
            sx={{ color: "rgba(255,255,255,0.5)" }}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          <ScriptViewer content={viewerContent} />
        </DialogContent>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
          sx={{
            backgroundColor:
              snackbar.severity === "success"
                ? "rgba(16,185,129,0.15)"
                : "rgba(239,68,68,0.15)",
            color: snackbar.severity === "success" ? "#10b981" : "#ef4444",
            border: `1px solid ${
              snackbar.severity === "success"
                ? "rgba(16,185,129,0.3)"
                : "rgba(239,68,68,0.3)"
            }`,
          }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
