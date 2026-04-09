import { useState, useEffect, useCallback } from "react";
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
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
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
  analyzeReferenceStyle,
} from "../lib/api";
import { Button } from "@mui/material";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import StyleIcon from "@mui/icons-material/Style";

const BUCKETS = [
  { key: "reference-thumbs", label: "Reference Thumbnails", accept: "image/*" },
  { key: "personal-photos", label: "Personal Photos", accept: "image/*" },
  { key: "logos", label: "Logos", accept: "image/*" },
  { key: "outputs", label: "Generated Outputs", accept: "image/*" },
  { key: "scripts", label: "Scripts", accept: ".md" },
  { key: "fonts", label: "Fonts", accept: ".ttf,.otf,.woff" },
];

interface AssetFile {
  name: string;
  public_url?: string;
  metadata?: { size?: number };
}

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
  const [analyzingStyle, setAnalyzingStyle] = useState(false);
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerContent, setViewerContent] = useState("");
  const [viewerTitle, setViewerTitle] = useState("");

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
        message: `Uploaded ${succeeded} file${
          succeeded !== 1 ? "s" : ""
        }. ${failed} failed.`,
        severity: "error",
      });
    } else {
      setSnackbar({
        open: true,
        message: `${succeeded} file${
          succeeded !== 1 ? "s" : ""
        } uploaded successfully`,
        severity: "success",
      });
    }

    // Clear file list after a delay so user can see final states
    setTimeout(() => setFileStatuses([]), 3000);
  };

  const handleDelete = async (name: string) => {
    await deleteAsset(currentBucket.key, name);
    loadFiles();
    setSnackbar({
      open: true,
      message: `${name} deleted`,
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
        message: `Indexed ${result.indexed} new photos (${result.skipped} already indexed, ${result.total} total)`,
        severity: "success",
      });
    } catch {
      setSnackbar({
        open: true,
        message: "Failed to reindex photos",
        severity: "error",
      });
    } finally {
      setReindexing(false);
    }
  };

  const handleAnalyzeStyle = async () => {
    setAnalyzingStyle(true);
    try {
      await analyzeReferenceStyle();
      setSnackbar({
        open: true,
        message: "Style analysis complete. Text style saved to your persona.",
        severity: "success",
      });
    } catch {
      setSnackbar({
        open: true,
        message: "Failed to analyze reference style",
        severity: "error",
      });
    } finally {
      setAnalyzingStyle(false);
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
    } catch {
      setSnackbar({
        open: true,
        message: "Failed to load script",
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
        Assets
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
          <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
            <AssetUpload
              onUpload={handleUpload}
              accept={currentBucket.accept}
              fileStatuses={fileStatuses}
            />
            {currentBucket.key === "reference-thumbs" && (
              <Button
                variant="outlined"
                startIcon={<StyleIcon />}
                onClick={handleAnalyzeStyle}
                disabled={analyzingStyle}
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
                {analyzingStyle ? "Analyzing..." : "Analyze Style"}
              </Button>
            )}
            {currentBucket.key === "personal-photos" && (
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
                {reindexing ? "Indexing..." : "Index Photos"}
              </Button>
            )}
          </Box>
        </Box>
      )}

      {loading ? (
        <Typography color="text.secondary">Loading...</Typography>
      ) : (
        <AssetGrid
          files={files}
          bucket={currentBucket.key}
          onDelete={handleDelete}
          onDownload={handleDownload}
          onView={
            currentBucket.key === "scripts" ? handleViewScript : undefined
          }
        />
      )}

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
