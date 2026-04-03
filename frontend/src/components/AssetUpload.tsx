import { useCallback } from "react";
import { Box, Typography } from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";

interface AssetUploadProps {
  onUpload: (files: FileList) => void;
  accept?: string;
}

export default function AssetUpload({ onUpload, accept }: AssetUploadProps) {
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
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

  return (
    <Box
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      sx={{
        border: "2px dashed rgba(124,58,237,0.3)",
        borderRadius: 2,
        p: 3,
        textAlign: "center",
        cursor: "pointer",
        transition: "border-color 0.2s",
        "&:hover": { borderColor: "#7c3aed" },
      }}
      onClick={() => document.getElementById("asset-upload-input")?.click()}
    >
      <input
        id="asset-upload-input"
        type="file"
        multiple
        hidden
        accept={accept}
        onChange={handleChange}
      />
      <CloudUploadIcon sx={{ fontSize: 40, color: "rgba(124,58,237,0.5)", mb: 1 }} />
      <Typography variant="body2" color="text.secondary">
        Drag & drop files here, or click to browse
      </Typography>
    </Box>
  );
}
