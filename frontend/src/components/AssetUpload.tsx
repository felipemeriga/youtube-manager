import { useCallback, useState } from "react";
import {
  Box,
  Typography,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
} from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import HourglassTopIcon from "@mui/icons-material/HourglassTop";
import UploadFileIcon from "@mui/icons-material/UploadFile";

export type FileUploadStatus = "pending" | "uploading" | "done" | "error";

export interface FileUploadItem {
  name: string;
  status: FileUploadStatus;
}

interface AssetUploadProps {
  onUpload: (files: FileList) => void;
  accept?: string;
  fileStatuses?: FileUploadItem[];
}

const statusIcon: Record<FileUploadStatus, React.ReactNode> = {
  pending: (
    <HourglassTopIcon sx={{ color: "rgba(255,255,255,0.3)", fontSize: 20 }} />
  ),
  uploading: (
    <UploadFileIcon
      sx={{ color: "#7c3aed", fontSize: 20, animation: "pulse 1.5s infinite" }}
    />
  ),
  done: <CheckCircleIcon sx={{ color: "#10b981", fontSize: 20 }} />,
  error: <ErrorIcon sx={{ color: "#ef4444", fontSize: 20 }} />,
};

export default function AssetUpload({
  onUpload,
  accept,
  fileStatuses,
}: AssetUploadProps) {
  const [dragOver, setDragOver] = useState(false);

  const isUploading =
    fileStatuses &&
    fileStatuses.some(
      (f) => f.status === "uploading" || f.status === "pending"
    );

  const completedCount =
    fileStatuses?.filter((f) => f.status === "done").length ?? 0;
  const totalCount = fileStatuses?.length ?? 0;
  const progressPercent =
    totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

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

  return (
    <Box>
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
            : isUploading
            ? "rgba(124,58,237,0.5)"
            : "rgba(124,58,237,0.3)",
          borderRadius: 2,
          p: 3,
          textAlign: "center",
          cursor: isUploading ? "default" : "pointer",
          transition: "all 0.2s",
          backgroundColor: dragOver ? "rgba(124,58,237,0.08)" : "transparent",
          "&:hover": isUploading ? {} : { borderColor: "#7c3aed" },
        }}
        onClick={() => {
          if (!isUploading) {
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
          disabled={!!isUploading}
        />
        <CloudUploadIcon
          sx={{
            fontSize: 40,
            color: isUploading ? "#7c3aed" : "rgba(124,58,237,0.5)",
            mb: 1,
            ...(isUploading ? { animation: "pulse 1.5s infinite" } : {}),
          }}
        />
        <Typography variant="body2" color="text.secondary">
          {isUploading
            ? `Enviando ${completedCount}/${totalCount}...`
            : dragOver
            ? "Solte os arquivos aqui"
            : "Arraste arquivos aqui ou clique para procurar"}
        </Typography>
        {isUploading && (
          <LinearProgress
            variant="determinate"
            value={progressPercent}
            sx={{
              height: 6,
              borderRadius: 3,
              mx: "auto",
              mt: 1.5,
              maxWidth: 300,
              backgroundColor: "rgba(124,58,237,0.15)",
              "& .MuiLinearProgress-bar": {
                borderRadius: 3,
                background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
              },
            }}
          />
        )}
      </Box>

      {fileStatuses && fileStatuses.length > 0 && (
        <List
          dense
          sx={{
            mt: 1.5,
            maxHeight: 240,
            overflow: "auto",
            backgroundColor: "rgba(255,255,255,0.02)",
            borderRadius: 2,
            border: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          {fileStatuses.map((file) => (
            <ListItem
              key={file.name}
              sx={{
                py: 0.5,
                opacity: file.status === "pending" ? 0.5 : 1,
                transition: "opacity 0.3s",
              }}
            >
              <ListItemIcon sx={{ minWidth: 32 }}>
                {statusIcon[file.status]}
              </ListItemIcon>
              <ListItemText
                primary={file.name}
                primaryTypographyProps={{
                  variant: "body2",
                  noWrap: true,
                  color:
                    file.status === "error"
                      ? "#ef4444"
                      : file.status === "done"
                      ? "#10b981"
                      : "text.secondary",
                }}
              />
            </ListItem>
          ))}
        </List>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </Box>
  );
}
