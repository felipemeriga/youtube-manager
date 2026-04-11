import { useState, KeyboardEvent } from "react";
import {
  Box,
  TextField,
  IconButton,
  Select,
  MenuItem,
  FormControl,
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";

interface ModelOption {
  id: string;
  label: string;
}

interface ChatInputProps {
  onSend: (content: string) => void;
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

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

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
      <Box sx={{ display: "flex", gap: 1, alignItems: "flex-end" }}>
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
          disabled={!value.trim() || disabled}
          sx={{
            width: 40,
            height: 40,
            borderRadius: 2.5,
            background:
              value.trim() && !disabled
                ? "linear-gradient(135deg, #7c3aed, #3b82f6)"
                : "rgba(255,255,255,0.05)",
            color: value.trim() && !disabled ? "#fff" : "rgba(255,255,255,0.2)",
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
