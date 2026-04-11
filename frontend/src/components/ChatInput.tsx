import { useState, useRef, KeyboardEvent } from "react";
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
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import CloseIcon from "@mui/icons-material/Close";
import { uploadAsset } from "../lib/api";

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

export default function ChatInput({
  onSend,
  disabled,
  models,
  selectedModel,
  onModelChange,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const [attachedImage, setAttachedImage] = useState<{
    file: File;
    preview: string;
    storagePath: string | null;
  } | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    setAttachedImage({ file, preview, storagePath: null });
    setUploading(true);

    try {
      const result = await uploadAsset("outputs", file);
      setAttachedImage((prev) =>
        prev ? { ...prev, storagePath: result.path } : null,
      );
    } catch {
      setAttachedImage(null);
    } finally {
      setUploading(false);
      // Reset file input so the same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleRemoveImage = () => {
    if (attachedImage?.preview) URL.revokeObjectURL(attachedImage.preview);
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
                <em>Modelo padr&atilde;o</em>
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
          <Box
            component="img"
            src={attachedImage.preview}
            alt="Imagem anexada"
            sx={{
              width: 48,
              height: 48,
              objectFit: "cover",
              borderRadius: 1,
            }}
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

        {/* Attach button */}
        <Tooltip title="Anexar imagem">
          <IconButton
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || uploading}
            sx={{
              width: 40,
              height: 40,
              borderRadius: 2.5,
              color: attachedImage
                ? "#7c3aed"
                : "rgba(255,255,255,0.4)",
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
    </Box>
  );
}
