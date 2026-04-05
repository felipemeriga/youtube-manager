import { Box, ImageList, ImageListItem, IconButton, Typography } from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadIcon from "@mui/icons-material/Download";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";

interface AssetFile {
  name: string;
  public_url?: string;
  metadata?: { size?: number };
}

interface AssetGridProps {
  files: AssetFile[];
  bucket: string;
  onDelete: (name: string) => void;
  onDownload: (name: string) => void;
}

function isImage(name: string) {
  return /\.(png|jpg|jpeg|gif|webp|svg)$/i.test(name);
}

export default function AssetGrid({ files, bucket, onDelete, onDownload }: AssetGridProps) {
  if (files.length === 0) {
    return (
      <Box sx={{ textAlign: "center", py: 4 }}>
        <Typography color="text.secondary">No files yet</Typography>
      </Box>
    );
  }

  return (
    <ImageList cols={4} gap={12}>
      {files.map((file) => (
        <ImageListItem
          key={file.name}
          sx={{
            borderRadius: 2,
            overflow: "hidden",
            border: "1px solid rgba(255,255,255,0.08)",
            backgroundColor: "rgba(255,255,255,0.03)",
            position: "relative",
            "&:hover .actions": { opacity: 1 },
          }}
        >
          {isImage(file.name) ? (
            <Box
              component="img"
              src={file.public_url || `/api/assets/${bucket}/${file.name}`}
              alt={file.name}
              sx={{ width: "100%", height: 150, objectFit: "cover" }}
            />
          ) : (
            <Box
              sx={{
                width: "100%",
                height: 150,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <InsertDriveFileIcon sx={{ fontSize: 48, color: "rgba(255,255,255,0.2)" }} />
            </Box>
          )}

          <Box sx={{ p: 1 }}>
            <Typography variant="caption" noWrap color="text.secondary">
              {file.name}
            </Typography>
          </Box>

          <Box
            className="actions"
            sx={{
              position: "absolute",
              top: 4,
              right: 4,
              display: "flex",
              gap: 0.5,
              opacity: 0,
              transition: "opacity 0.2s",
            }}
          >
            <IconButton
              size="small"
              onClick={() => onDownload(file.name)}
              sx={{ backgroundColor: "rgba(0,0,0,0.6)", color: "#fff" }}
            >
              <DownloadIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={() => onDelete(file.name)}
              sx={{ backgroundColor: "rgba(0,0,0,0.6)", color: "#ef4444" }}
            >
              <DeleteOutlineIcon fontSize="small" />
            </IconButton>
          </Box>
        </ImageListItem>
      ))}
    </ImageList>
  );
}
