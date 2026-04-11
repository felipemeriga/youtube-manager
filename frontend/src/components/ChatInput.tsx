import { useState, useRef, useEffect, KeyboardEvent } from "react";
import {
  Box,
  TextField,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  Tooltip,
  Typography,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  Tabs,
  Tab,
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import PhotoLibraryIcon from "@mui/icons-material/PhotoLibrary";
import CloseIcon from "@mui/icons-material/Close";
import { uploadAsset, listAssets } from "../lib/api";
import { supabase } from "../lib/supabase";

interface ModelOption {
  id: string;
  label: string;
}

interface ChatInputProps {
  onSend: (content: string, imageUrl?: string) => void;
  disabled?: boolean;
  models?: ModelOption[];
  selectedModel?: string;
  onModelChange?: (model: string) => void;
}

interface StorageFile {
  name: string;
  public_url?: string;
}

const BROWSABLE_BUCKETS = [
  { key: "outputs", label: "Resultados" },
  { key: "personal-photos", label: "Fotos Pessoais" },
  { key: "reference-thumbs", label: "Referências" },
  { key: "logos", label: "Logos" },
];

export default function ChatInput({
  onSend,
  disabled,
  models,
  selectedModel,
  onModelChange,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const [attachedImage, setAttachedImage] = useState<{
    preview: string;
    storagePath: string;
    fromBrowser?: boolean;
  } | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [browserOpen, setBrowserOpen] = useState(false);

  const handleSend = () => {
    const trimmed = value.trim();
    if ((!trimmed && !attachedImage) || disabled) return;
    onSend(trimmed, attachedImage?.storagePath ?? undefined);
    setValue("");
    setAttachedImage(null);
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const preview = URL.createObjectURL(file);
    setAttachedImage({ preview, storagePath: "" });
    setUploading(true);

    try {
      const result = await uploadAsset("outputs", file);
      setAttachedImage({ preview, storagePath: result.path });
    } catch {
      setAttachedImage(null);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleBrowserSelect = (bucket: string, file: StorageFile) => {
    const fullPath = `${bucket}/${file.name}`;
    // Use public_url for preview if available, otherwise proxy
    const preview = file.public_url || `/api/assets/${bucket}/${file.name}`;
    setAttachedImage({ preview, storagePath: fullPath, fromBrowser: true });
    setBrowserOpen(false);
  };

  const handleRemoveImage = () => {
    if (attachedImage && !attachedImage.fromBrowser) {
      URL.revokeObjectURL(attachedImage.preview);
    }
    setAttachedImage(null);
  };

  const canSend =
    (value.trim() || attachedImage?.storagePath) && !disabled && !uploading;

  return (
    <Box
      sx={{
        p: 2,
        borderTop: "1px solid rgba(255,255,255,0.06)",
        backgroundColor: "rgba(12, 12, 18, 0.8)",
        backdropFilter: "blur(16px)",
      }}
    >
      {models && onModelChange && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <Select
              value={selectedModel || ""}
              displayEmpty
              onChange={(e) => onModelChange(e.target.value)}
              sx={{
                fontSize: "0.75rem",
                color: "rgba(255,255,255,0.6)",
                borderRadius: 2,
                "& .MuiOutlinedInput-notchedOutline": {
                  borderColor: "rgba(255,255,255,0.08)",
                },
                "&:hover .MuiOutlinedInput-notchedOutline": {
                  borderColor: "rgba(255,255,255,0.15)",
                },
                height: 28,
                transition: "all 0.2s ease",
              }}
            >
              <MenuItem value="">
                <em>Modelo padrão</em>
              </MenuItem>
              {models.map((m) => (
                <MenuItem key={m.id} value={m.id}>
                  {m.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      )}

      {/* Attached image preview */}
      {attachedImage && (
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            mb: 1,
            p: 1,
            borderRadius: 2,
            backgroundColor: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <AuthPreviewImage
            src={attachedImage.preview}
            fromBrowser={attachedImage.fromBrowser}
          />
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              variant="caption"
              sx={{ color: "rgba(255,255,255,0.7)" }}
            >
              Imagem anexada
            </Typography>
            {uploading && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                <CircularProgress size={12} />
                <Typography
                  variant="caption"
                  sx={{ color: "rgba(255,255,255,0.4)" }}
                >
                  Enviando...
                </Typography>
              </Box>
            )}
          </Box>
          <Tooltip title="Remover">
            <IconButton
              size="small"
              onClick={handleRemoveImage}
              sx={{ color: "rgba(255,255,255,0.4)" }}
            >
              <CloseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      <Box sx={{ display: "flex", gap: 1, alignItems: "flex-end" }}>
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          style={{ display: "none" }}
          onChange={handleFileSelect}
        />

        {/* Attach from file */}
        <Tooltip title="Enviar imagem">
          <IconButton
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || uploading}
            sx={{
              width: 40,
              height: 40,
              borderRadius: 2.5,
              color: "rgba(255,255,255,0.4)",
              transition: "all 0.2s ease",
              "&:hover": {
                color: "#7c3aed",
                backgroundColor: "rgba(124,58,237,0.08)",
              },
            }}
          >
            <AttachFileIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        {/* Browse storage */}
        <Tooltip title="Usar imagem existente">
          <IconButton
            onClick={() => setBrowserOpen(true)}
            disabled={disabled || uploading}
            sx={{
              width: 40,
              height: 40,
              borderRadius: 2.5,
              color: attachedImage?.fromBrowser
                ? "#7c3aed"
                : "rgba(255,255,255,0.4)",
              transition: "all 0.2s ease",
              "&:hover": {
                color: "#7c3aed",
                backgroundColor: "rgba(124,58,237,0.08)",
              },
            }}
          >
            <PhotoLibraryIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <TextField
          fullWidth
          multiline
          maxRows={4}
          placeholder="Digite uma mensagem..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 2.5,
              backgroundColor: "rgba(255,255,255,0.04)",
              backdropFilter: "blur(10px)",
              transition: "all 0.2s ease",
              "&:hover": { backgroundColor: "rgba(255,255,255,0.06)" },
              "&.Mui-focused": { backgroundColor: "rgba(255,255,255,0.06)" },
            },
          }}
        />
        <IconButton
          onClick={handleSend}
          disabled={!canSend}
          sx={{
            width: 40,
            height: 40,
            borderRadius: 2.5,
            background: canSend
              ? "linear-gradient(135deg, #7c3aed, #3b82f6)"
              : "rgba(255,255,255,0.05)",
            color: canSend ? "#fff" : "rgba(255,255,255,0.2)",
            transition: "all 0.2s ease",
            "&:hover": {
              background: "linear-gradient(135deg, #6d28d9, #2563eb)",
            },
            "&:disabled": {
              background: "rgba(255,255,255,0.05)",
              color: "rgba(255,255,255,0.2)",
            },
          }}
        >
          <SendIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Storage browser dialog */}
      <StorageBrowserDialog
        open={browserOpen}
        onClose={() => setBrowserOpen(false)}
        onSelect={handleBrowserSelect}
      />
    </Box>
  );
}

/** Small preview image that handles auth for /api/assets/ URLs */
function AuthPreviewImage({
  src,
  fromBrowser,
}: {
  src: string;
  fromBrowser?: boolean;
}) {
  const [imgSrc, setImgSrc] = useState(src);

  useEffect(() => {
    if (!fromBrowser || !src.startsWith("/api/assets/")) {
      setImgSrc(src);
      return;
    }
    let revoke: string | null = null;
    const load = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) return;
      try {
        const res = await fetch(src, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (res.ok) {
          const blob = await res.blob();
          revoke = URL.createObjectURL(blob);
          setImgSrc(revoke);
        }
      } catch {
        // fallback to original src
      }
    };
    load();
    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [src, fromBrowser]);

  return (
    <Box
      component="img"
      src={imgSrc}
      alt="Imagem anexada"
      sx={{
        width: 48,
        height: 48,
        objectFit: "cover",
        borderRadius: 1,
      }}
    />
  );
}

/** Dialog to browse existing storage files */
function StorageBrowserDialog({
  open,
  onClose,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  onSelect: (bucket: string, file: StorageFile) => void;
}) {
  const [tab, setTab] = useState(0);
  const [files, setFiles] = useState<StorageFile[]>([]);
  const [loading, setLoading] = useState(false);

  const currentBucket = BROWSABLE_BUCKETS[tab];

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    listAssets(currentBucket.key)
      .then((data) => {
        setFiles(
          (data as unknown as StorageFile[]).filter(
            (f) => f.name && /\.(png|jpg|jpeg|gif|webp)$/i.test(f.name),
          ),
        );
      })
      .catch(() => setFiles([]))
      .finally(() => setLoading(false));
  }, [open, currentBucket.key]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: "#1a1a2e",
          backgroundImage: "none",
          borderRadius: 3,
          maxHeight: "70vh",
        },
      }}
    >
      <DialogTitle
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          pb: 1,
        }}
      >
        <Typography variant="h6" sx={{ color: "#e2e8f0", fontWeight: 600 }}>
          Usar imagem existente
        </Typography>
        <IconButton onClick={onClose} sx={{ color: "#94a3b8" }}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      <DialogContent sx={{ p: 0 }}>
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          sx={{
            px: 2,
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            "& .MuiTab-root": {
              textTransform: "none",
              color: "rgba(255,255,255,0.5)",
              "&.Mui-selected": { color: "#a78bfa" },
            },
            "& .MuiTabs-indicator": { backgroundColor: "#7c3aed" },
          }}
        >
          {BROWSABLE_BUCKETS.map((b) => (
            <Tab key={b.key} label={b.label} />
          ))}
        </Tabs>

        <Box sx={{ p: 2 }}>
          {loading ? (
            <Box
              sx={{
                display: "flex",
                justifyContent: "center",
                py: 4,
              }}
            >
              <CircularProgress size={24} sx={{ color: "#7c3aed" }} />
            </Box>
          ) : files.length === 0 ? (
            <Typography
              color="text.secondary"
              sx={{ textAlign: "center", py: 4 }}
            >
              Nenhuma imagem nesta pasta
            </Typography>
          ) : (
            <Box
              sx={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                gap: 1.5,
              }}
            >
              {files.map((file) => (
                <StorageThumbnail
                  key={file.name}
                  file={file}
                  bucket={currentBucket.key}
                  onClick={() => onSelect(currentBucket.key, file)}
                />
              ))}
            </Box>
          )}
        </Box>
      </DialogContent>
    </Dialog>
  );
}

/** Thumbnail card in the storage browser */
function StorageThumbnail({
  file,
  bucket,
  onClick,
}: {
  file: StorageFile;
  bucket: string;
  onClick: () => void;
}) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let revoke: string | null = null;
    const load = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) return;
      try {
        const res = await fetch(`/api/assets/${bucket}/${file.name}`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (res.ok) {
          const blob = await res.blob();
          revoke = URL.createObjectURL(blob);
          setSrc(revoke);
        }
      } catch {
        // ignore
      }
    };
    load();
    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [bucket, file.name]);

  return (
    <Box
      onClick={onClick}
      sx={{
        borderRadius: 2,
        overflow: "hidden",
        cursor: "pointer",
        border: "2px solid transparent",
        transition: "all 0.2s",
        "&:hover": {
          borderColor: "#7c3aed",
          transform: "scale(1.03)",
        },
      }}
    >
      {src ? (
        <Box
          component="img"
          src={src}
          alt={file.name}
          sx={{
            width: "100%",
            height: 100,
            objectFit: "cover",
            display: "block",
          }}
        />
      ) : (
        <Box
          sx={{
            width: "100%",
            height: 100,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "rgba(255,255,255,0.03)",
          }}
        >
          <CircularProgress size={16} sx={{ color: "#7c3aed" }} />
        </Box>
      )}
      <Box sx={{ px: 0.5, py: 0.25 }}>
        <Typography
          variant="caption"
          sx={{
            color: "rgba(255,255,255,0.5)",
            fontSize: 10,
            display: "block",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {file.name}
        </Typography>
      </Box>
    </Box>
  );
}
