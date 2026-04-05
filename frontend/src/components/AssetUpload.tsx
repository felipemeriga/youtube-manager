import { useCallback, useState } from "react";
import { Box, Typography, LinearProgress } from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";

interface AssetUploadProps {
  onUpload: (files: FileList) => void;
  accept?: string;
  uploading?: boolean;
  uploadProgress?: { current: number; total: number };
}

export default function AssetUpload({
  onUpload,
  accept,
  uploading,
  uploadProgress,
}: AssetUploadProps) {
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        onUpload(e.dataTransfer.files);
      }
    },
    [onUpload]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        onUpload(e.target.files);
      }
    },
    [onUpload]
  );

  const progressPercent =
    uploadProgress && uploadProgress.total > 0
      ? (uploadProgress.current / uploadProgress.total) * 100
      : 0;

  return (
    <Box
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      sx={{
        border: "2px dashed",
        borderColor: dragOver
          ? "#7c3aed"
          : uploading
            ? "rgba(124,58,237,0.5)"
            : "rgba(124,58,237,0.3)",
        borderRadius: 2,
        p: 3,
        textAlign: "center",
        cursor: uploading ? "default" : "pointer",
        transition: "all 0.2s",
        backgroundColor: dragOver
          ? "rgba(124,58,237,0.08)"
          : "transparent",
        "&:hover": uploading ? {} : { borderColor: "#7c3aed" },
        position: "relative",
        overflow: "hidden",
      }}
      onClick={() => {
        if (!uploading) {
          document.getElementById("asset-upload-input")?.click();
        }
      }}
    >
      <input
        id="asset-upload-input"
        type="file"
        multiple
        hidden
        accept={accept}
        onChange={handleChange}
        disabled={uploading}
      />

      {uploading ? (
        <>
          <CloudUploadIcon
            sx={{ fontSize: 40, color: "#7c3aed", mb: 1, animation: "pulse 1.5s infinite" }}
          />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Uploading {uploadProgress?.current}/{uploadProgress?.total}...
          </Typography>
          <LinearProgress
            variant="determinate"
            value={progressPercent}
            sx={{
              height: 6,
              borderRadius: 3,
              mx: "auto",
              maxWidth: 300,
              backgroundColor: "rgba(124,58,237,0.15)",
              "& .MuiLinearProgress-bar": {
                borderRadius: 3,
                background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
              },
            }}
          />
          <style>{`
            @keyframes pulse {
              0%, 100% { opacity: 1; }
              50% { opacity: 0.5; }
            }
          `}</style>
        </>
      ) : (
        <>
          <CloudUploadIcon
            sx={{ fontSize: 40, color: "rgba(124,58,237,0.5)", mb: 1 }}
          />
          <Typography variant="body2" color="text.secondary">
            {dragOver
              ? "Drop files to upload"
              : "Drag & drop files here, or click to browse"}
          </Typography>
        </>
      )}
    </Box>
  );
}
