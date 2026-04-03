import { useState, useEffect, useCallback } from "react";
import { Box, Typography, Tabs, Tab } from "@mui/material";
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
  metadata?: { size?: number };
}

export default function AssetsPage() {
  const [activeTab, setActiveTab] = useState(0);
  const [files, setFiles] = useState<AssetFile[]>([]);
  const [loading, setLoading] = useState(false);

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
    for (let i = 0; i < fileList.length; i++) {
      await uploadAsset(currentBucket.key, fileList[i]);
    }
    loadFiles();
  };

  const handleDelete = async (name: string) => {
    await deleteAsset(currentBucket.key, name);
    loadFiles();
  };

  const handleDownload = (name: string) => {
    window.open(`/api/assets/${currentBucket.key}/${name}`, "_blank");
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
          <AssetUpload onUpload={handleUpload} accept={currentBucket.accept} />
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
    </Box>
  );
}
