import {
  Box,
  IconButton,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Typography,
} from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadIcon from "@mui/icons-material/Download";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import FontDownloadIcon from "@mui/icons-material/FontDownload";

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

function FileList({
  files,
  onDelete,
  onDownload,
}: {
  files: AssetFile[];
  onDelete: (name: string) => void;
  onDownload: (name: string) => void;
}) {
  return (
    <List
      sx={{
        backgroundColor: "rgba(255,255,255,0.02)",
        borderRadius: 2,
        border: "1px solid rgba(255,255,255,0.08)",
      }}
    >
      {files.map((file) => (
        <ListItem
          key={file.name}
          secondaryAction={
            <Box sx={{ display: "flex", gap: 0.5 }}>
              <IconButton
                size="small"
                onClick={() => onDownload(file.name)}
                sx={{ color: "rgba(255,255,255,0.5)" }}
              >
                <DownloadIcon fontSize="small" />
              </IconButton>
              <IconButton
                size="small"
                onClick={() => onDelete(file.name)}
                sx={{ color: "#ef4444" }}
              >
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            </Box>
          }
          sx={{
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            "&:last-child": { borderBottom: "none" },
          }}
        >
          <ListItemIcon sx={{ minWidth: 40 }}>
            <FontDownloadIcon sx={{ color: "rgba(124,58,237,0.6)" }} />
          </ListItemIcon>
          <ListItemText
            primary={file.name}
            primaryTypographyProps={{
              variant: "body2",
              color: "text.secondary",
            }}
          />
        </ListItem>
      ))}
    </List>
  );
}

export default function AssetGrid({
  files,
  bucket,
  onDelete,
  onDownload,
}: AssetGridProps) {
  if (files.length === 0) {
    return (
      <Box sx={{ textAlign: "center", py: 4 }}>
        <Typography color="text.secondary">No files yet</Typography>
      </Box>
    );
  }

  if (bucket === "fonts") {
    return (
      <FileList files={files} onDelete={onDelete} onDownload={onDownload} />
    );
  }

  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 2,
      }}
    >
      {files.map((file) => (
        <Box
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
              sx={{
                width: "100%",
                height: 280,
                objectFit: "cover",
                display: "block",
              }}
            />
          ) : (
            <Box
              sx={{
                width: "100%",
                height: 280,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <InsertDriveFileIcon
                sx={{ fontSize: 48, color: "rgba(255,255,255,0.2)" }}
              />
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
        </Box>
      ))}
    </Box>
  );
}
