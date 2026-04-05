import { useState, useEffect, useCallback } from "react";
import { Box, Typography, Tabs, Tab, Snackbar, Alert } from "@mui/material";
import AssetGrid from "../components/AssetGrid";
import AssetUpload from "../components/AssetUpload";
import { listAssets, uploadAsset, deleteAsset } from "../lib/api";

const BUCKETS = [
  { key: "reference-thumbs", label: "Reference Thumbnails", accept: "image/*" },
  { key: "personal-photos", label: "Personal Photos", accept: "image/*" },
  { key: "fonts", label: "Fonts", accept: ".ttf,.otf,.woff,.woff2" },
  { key: "outputs", label: "Generated Outputs", accept: "image/*" },
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
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0 });
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({ open: false, message: "", severity: "success" });

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
    const total = fileList.length;
    setUploading(true);
    setUploadProgress({ current: 0, total });

    let succeeded = 0;
    let failed = 0;

    for (let i = 0; i < total; i++) {
      try {
        await uploadAsset(currentBucket.key, fileList[i]);
        succeeded++;
      } catch {
        failed++;
      }
      setUploadProgress({ current: i + 1, total });
    }

    setUploading(false);
    loadFiles();

    if (failed > 0) {
      setSnackbar({
        open: true,
        message: `Uploaded ${succeeded} file${succeeded !== 1 ? "s" : ""}. ${failed} failed.`,
        severity: "error",
      });
    } else {
      setSnackbar({
        open: true,
        message: `${succeeded} file${succeeded !== 1 ? "s" : ""} uploaded successfully`,
        severity: "success",
      });
    }
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

  return (
    <Box sx={{ flex: 1, display: "flex", flexDirection: "column", p: 3, overflow: "auto" }}>
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

      {currentBucket.key !== "outputs" && (
        <Box sx={{ mb: 3 }}>
          <AssetUpload
            onUpload={handleUpload}
            accept={currentBucket.accept}
            uploading={uploading}
            uploadProgress={uploadProgress}
          />
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
        />
      )}

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
            border: `1px solid ${snackbar.severity === "success" ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)"}`,
          }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
