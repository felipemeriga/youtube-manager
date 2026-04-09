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
        borderTop: "1px solid rgba(255,255,255,0.08)",
        backgroundColor: "rgba(0,0,0,0.2)",
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
                color: "rgba(255,255,255,0.7)",
                "& .MuiOutlinedInput-notchedOutline": {
                  borderColor: "rgba(255,255,255,0.1)",
                },
                "&:hover .MuiOutlinedInput-notchedOutline": {
                  borderColor: "rgba(255,255,255,0.2)",
                },
                height: 28,
              }}
            >
              <MenuItem value="">
                <em>Default model</em>
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
          placeholder="Describe the thumbnail you want..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 2,
              backgroundColor: "rgba(255,255,255,0.05)",
            },
          }}
        />
        <IconButton
          onClick={handleSend}
          disabled={!value.trim() || disabled}
          sx={{
            color: "#7c3aed",
            "&:disabled": { color: "rgba(255,255,255,0.2)" },
          }}
        >
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
