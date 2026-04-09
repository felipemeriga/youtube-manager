import { Box, IconButton, Typography } from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadIcon from "@mui/icons-material/Download";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import DescriptionIcon from "@mui/icons-material/Description";

interface AssetFile {
  name: string;
  public_url?: string;
  metadata?: { size?: number };
  created_at?: string;
}

interface AssetGridProps {
  files: AssetFile[];
  bucket: string;
  onDelete: (name: string) => void;
  onDownload: (name: string) => void;
  onView?: (name: string) => void;
}

function isImage(name: string) {
  return /\.(png|jpg|jpeg|gif|webp|svg)$/i.test(name);
}

function formatDate(dateStr?: string) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatSize(size?: number) {
  if (!size) return "";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatScriptName(name: string) {
  return name
    .replace(/\.md$/, "")
    .replace(/-\d{8}-\d{6}$/, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

import VisibilityIcon from "@mui/icons-material/Visibility";

function AssetList({
  files,
  onDelete,
  onDownload,
  onView,
}: Omit<AssetGridProps, "bucket">) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      {files.map((file) => (
        <Box
          key={file.name}
          onClick={() => onView?.(file.name)}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 2,
            p: 2,
            borderRadius: 2,
            border: "1px solid rgba(255,255,255,0.08)",
            backgroundColor: "rgba(255,255,255,0.03)",
            cursor: onView ? "pointer" : "default",
            "&:hover": {
              backgroundColor: "rgba(255,255,255,0.06)",
              borderColor: "rgba(124,58,237,0.3)",
            },
            transition: "all 0.2s",
          }}
        >
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: 1.5,
              background:
                "linear-gradient(135deg, rgba(124,58,237,0.2), rgba(59,130,246,0.2))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <DescriptionIcon sx={{ fontSize: 20, color: "#a78bfa" }} />
          </Box>

          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              variant="body2"
              sx={{
                color: "rgba(255,255,255,0.9)",
                fontWeight: 500,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {formatScriptName(file.name)}
            </Typography>
            <Box sx={{ display: "flex", gap: 2, mt: 0.25 }}>
              <Typography variant="caption" color="text.secondary">
                {formatDate(file.created_at)}
              </Typography>
              {file.metadata?.size && (
                <Typography variant="caption" color="text.secondary">
                  {formatSize(file.metadata.size)}
                </Typography>
              )}
            </Box>
          </Box>

          <Box
            sx={{ display: "flex", gap: 0.5, flexShrink: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            {onView && (
              <IconButton
                size="small"
                onClick={() => onView(file.name)}
                sx={{
                  color: "rgba(255,255,255,0.5)",
                  "&:hover": { color: "#7c3aed" },
                }}
              >
                <VisibilityIcon fontSize="small" />
              </IconButton>
            )}
            <IconButton
              size="small"
              onClick={() => onDownload(file.name)}
              sx={{
                color: "rgba(255,255,255,0.5)",
                "&:hover": { color: "#7c3aed" },
              }}
            >
              <DownloadIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={() => onDelete(file.name)}
              sx={{
                color: "rgba(255,255,255,0.5)",
                "&:hover": { color: "#ef4444" },
              }}
            >
              <DeleteOutlineIcon fontSize="small" />
            </IconButton>
          </Box>
        </Box>
      ))}
    </Box>
  );
}

export default function AssetGrid({
  files,
  bucket,
  onDelete,
  onDownload,
  onView,
}: AssetGridProps) {
  if (files.length === 0) {
    return (
      <Box sx={{ textAlign: "center", py: 4 }}>
        <Typography color="text.secondary">No files yet</Typography>
      </Box>
    );
  }

  if (bucket === "scripts") {
    return (
      <AssetList
        files={files}
        onDelete={onDelete}
        onDownload={onDownload}
        onView={onView}
      />
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
