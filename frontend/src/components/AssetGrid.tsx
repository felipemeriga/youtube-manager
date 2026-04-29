import { Box, Checkbox, IconButton, Typography } from "@mui/material";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadIcon from "@mui/icons-material/Download";
import InsertDriveFileIcon from "@mui/icons-material/InsertDriveFile";
import DescriptionIcon from "@mui/icons-material/Description";
import VisibilityIcon from "@mui/icons-material/Visibility";

interface AssetFile {
  name: string;
  public_url?: string;
  metadata?: { size?: number };
  created_at?: string;
}

const EMPTY_HINTS: Record<string, string> = {
  "reference-thumbs":
    "Faça upload de 3-5 thumbnails que representam seu estilo — o agente usa elas para definir layout, tipografia e composição.",
  "personal-photos":
    "Suba fotos suas em diferentes poses e expressões. O agente vai escolher a foto ideal para cada thumbnail.",
  logos:
    "Adicione o logo do canal. Ele será posicionado nas thumbnails seguindo as referências.",
  outputs:
    "Suas thumbnails geradas vão aparecer aqui depois de salvas em uma conversa.",
  scripts:
    "Os roteiros que você salvar nas conversas vão aparecer aqui.",
  fonts:
    "Suba arquivos .ttf, .otf ou .woff para que o agente use suas fontes na tipografia.",
};

interface AssetGridProps {
  files: AssetFile[];
  bucket: string;
  onDelete: (name: string) => void;
  onDownload: (name: string) => void;
  onView?: (name: string) => void;
  selected: Set<string>;
  onToggleSelect: (name: string) => void;
  onSelectAll: () => void;
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

const checkboxSx = {
  color: "rgba(255,255,255,0.3)",
  "&.Mui-checked": { color: "#7c3aed" },
  p: 0.5,
};

function AssetList({
  files,
  onDelete,
  onDownload,
  onView,
  selected,
  onToggleSelect,
  onSelectAll,
}: Omit<AssetGridProps, "bucket">) {
  const anySelected = selected.size > 0;
  const allSelected = files.length > 0 && files.every((f) => selected.has(f.name));

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
      {files.length > 0 && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5, pl: 1 }}>
          <Checkbox
            checked={allSelected}
            indeterminate={anySelected && !allSelected}
            onChange={onSelectAll}
            size="small"
            sx={checkboxSx}
          />
          <Typography variant="caption" color="text.secondary">
            Selecionar tudo
          </Typography>
        </Box>
      )}
      {files.map((file) => {
        const isSelected = selected.has(file.name);
        return (
          <Box
            key={file.name}
            onClick={() => onView?.(file.name)}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 2,
              p: 2,
              borderRadius: 2,
              border: isSelected
                ? "1px solid rgba(124,58,237,0.5)"
                : "1px solid rgba(255,255,255,0.08)",
              backgroundColor: isSelected
                ? "rgba(124,58,237,0.08)"
                : "rgba(255,255,255,0.03)",
              cursor: onView ? "pointer" : "default",
              boxShadow: isSelected
                ? "0 0 12px rgba(124,58,237,0.15)"
                : "none",
              "&:hover": {
                backgroundColor: isSelected
                  ? "rgba(124,58,237,0.12)"
                  : "rgba(255,255,255,0.06)",
                borderColor: "rgba(124,58,237,0.3)",
                "& .select-checkbox": {
                  opacity: 1,
                },
              },
              transition: "all 0.2s",
            }}
          >
            <Box
              className="select-checkbox"
              onClick={(e) => e.stopPropagation()}
              sx={{
                opacity: anySelected || isSelected ? 1 : 0,
                transition: "opacity 0.15s",
                flexShrink: 0,
              }}
            >
              <Checkbox
                checked={isSelected}
                onChange={() => onToggleSelect(file.name)}
                size="small"
                sx={checkboxSx}
              />
            </Box>

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
        );
      })}
    </Box>
  );
}

export default function AssetGrid({
  files,
  bucket,
  onDelete,
  onDownload,
  onView,
  selected,
  onToggleSelect,
  onSelectAll,
}: AssetGridProps) {
  if (files.length === 0) {
    const hint = EMPTY_HINTS[bucket] ?? "Nenhum arquivo aqui ainda.";
    return (
      <Box sx={{ textAlign: "center", py: 6, px: 2 }}>
        <Typography
          variant="body2"
          sx={{ color: "rgba(255,255,255,0.55)", fontWeight: 600, mb: 0.75 }}
        >
          Nenhum arquivo aqui ainda
        </Typography>
        <Typography
          variant="caption"
          sx={{ color: "rgba(255,255,255,0.4)", lineHeight: 1.5 }}
        >
          {hint}
        </Typography>
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
        selected={selected}
        onToggleSelect={onToggleSelect}
        onSelectAll={onSelectAll}
      />
    );
  }

  const anySelected = selected.size > 0;
  const allSelected = files.length > 0 && files.every((f) => selected.has(f.name));

  return (
    <Box>
      {files.length > 0 && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5, pl: 0.5 }}>
          <Checkbox
            checked={allSelected}
            indeterminate={anySelected && !allSelected}
            onChange={onSelectAll}
            size="small"
            sx={checkboxSx}
          />
          <Typography variant="caption" color="text.secondary">
            Selecionar tudo
          </Typography>
        </Box>
      )}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 2,
        }}
      >
        {files.map((file) => {
          const isSelected = selected.has(file.name);
          return (
            <Box
              key={file.name}
              sx={{
                borderRadius: 2,
                overflow: "hidden",
                border: isSelected
                  ? "1px solid rgba(124,58,237,0.5)"
                  : "1px solid rgba(255,255,255,0.08)",
                backgroundColor: isSelected
                  ? "rgba(124,58,237,0.08)"
                  : "rgba(255,255,255,0.03)",
                boxShadow: isSelected
                  ? "0 0 12px rgba(124,58,237,0.15)"
                  : "none",
                position: "relative",
                transition: "all 0.2s",
                "&:hover .actions": { opacity: 1 },
                "&:hover .select-checkbox": { opacity: 1 },
              }}
            >
              {/* Checkbox overlay */}
              <Box
                className="select-checkbox"
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleSelect(file.name);
                }}
                sx={{
                  position: "absolute",
                  top: 6,
                  left: 6,
                  zIndex: 2,
                  opacity: anySelected || isSelected ? 1 : 0,
                  transition: "opacity 0.15s",
                  backgroundColor: "rgba(0,0,0,0.5)",
                  borderRadius: 1,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Checkbox
                  checked={isSelected}
                  size="small"
                  sx={checkboxSx}
                  tabIndex={-1}
                />
              </Box>

              {isImage(file.name) ? (
                <Box
                  component="img"
                  src={file.public_url || `/api/assets/${bucket}/${file.name}`}
                  alt={file.name}
                  loading="lazy"
                  decoding="async"
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
          );
        })}
      </Box>
    </Box>
  );
}
