import { useState } from "react";
import {
  Box,
  Typography,
  Paper,
  Checkbox,
  IconButton,
  TextField,
  Button,
  Divider,
} from "@mui/material";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import CloseIcon from "@mui/icons-material/Close";
import AddIcon from "@mui/icons-material/Add";
import type { ScriptSection } from "../lib/api";

const DEFAULT_SECTION_NAMES = new Set([
  "Gancho / Abertura",
  "Tabela de Tempos",
  "Dados e Estatísticas",
  "Pontos de Discussão",
  "Roteiro Completo",
  "Fontes Verificadas",
]);

interface Props {
  sections: ScriptSection[];
  onChange: (sections: ScriptSection[]) => void;
}

export default function ScriptTemplateBuilder({ sections, onChange }: Props) {
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const sorted = [...sections].sort((a, b) => a.order - b.order);

  const reorder = (updated: ScriptSection[]) => {
    onChange(updated.map((s, i) => ({ ...s, order: i })));
  };

  const toggleEnabled = (index: number) => {
    const updated = [...sorted];
    updated[index] = { ...updated[index], enabled: !updated[index].enabled };
    reorder(updated);
  };

  const moveUp = (index: number) => {
    if (index === 0) return;
    const updated = [...sorted];
    [updated[index - 1], updated[index]] = [updated[index], updated[index - 1]];
    reorder(updated);
  };

  const moveDown = (index: number) => {
    if (index === sorted.length - 1) return;
    const updated = [...sorted];
    [updated[index], updated[index + 1]] = [updated[index + 1], updated[index]];
    reorder(updated);
  };

  const removeSection = (index: number) => {
    const updated = sorted.filter((_, i) => i !== index);
    reorder(updated);
  };

  const addSection = () => {
    if (!newName.trim() || !newDesc.trim()) return;
    const updated = [
      ...sorted,
      {
        name: newName.trim(),
        description: newDesc.trim(),
        enabled: true,
        order: sorted.length,
      },
    ];
    reorder(updated);
    setNewName("");
    setNewDesc("");
    setAdding(false);
  };

  return (
    <Paper
      sx={{
        width: "100%",
        maxWidth: 640,
        p: 4,
        mt: 3,
        display: "flex",
        flexDirection: "column",
        gap: 2,
      }}
    >
      <Typography variant="h5" sx={{ fontWeight: 600 }}>
        Modelo do Roteiro
      </Typography>
      <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.5)" }}>
        Personalize as seções incluídas nos roteiros gerados. Ative, reordene ou adicione seções personalizadas.
      </Typography>

      <Box>
        {sorted.map((section, index) => (
          <Box key={`${section.name}-${index}`}>
            {index > 0 && (
              <Divider sx={{ borderColor: "rgba(255,255,255,0.08)" }} />
            )}
            <Box
              sx={{
                display: "flex",
                alignItems: "flex-start",
                py: 1.5,
                opacity: section.enabled ? 1 : 0.4,
              }}
            >
              <Checkbox
                checked={section.enabled}
                onChange={() => toggleEnabled(index)}
                sx={{
                  color: "rgba(255,255,255,0.3)",
                  "&.Mui-checked": { color: "#7c3aed" },
                  mt: -0.5,
                }}
              />
              <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {section.name}
                </Typography>
                <Typography
                  variant="caption"
                  sx={{ color: "rgba(255,255,255,0.5)" }}
                >
                  {section.description}
                </Typography>
              </Box>
              <Box sx={{ display: "flex", gap: 0.5, ml: 1 }}>
                {!DEFAULT_SECTION_NAMES.has(section.name) && (
                  <IconButton
                    size="small"
                    onClick={() => removeSection(index)}
                    sx={{
                      color: "rgba(255,255,255,0.3)",
                      "&:hover": { color: "#ef4444" },
                    }}
                  >
                    <CloseIcon fontSize="small" />
                  </IconButton>
                )}
                <IconButton
                  size="small"
                  disabled={index === 0}
                  onClick={() => moveUp(index)}
                  sx={{ color: "rgba(255,255,255,0.3)" }}
                >
                  <ArrowUpwardIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  disabled={index === sorted.length - 1}
                  onClick={() => moveDown(index)}
                  sx={{ color: "rgba(255,255,255,0.3)" }}
                >
                  <ArrowDownwardIcon fontSize="small" />
                </IconButton>
              </Box>
            </Box>
          </Box>
        ))}
      </Box>

      {adding ? (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5, mt: 1 }}>
          <TextField
            label="Nome da Seção"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            size="small"
            fullWidth
          />
          <TextField
            label="Descrição"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            size="small"
            fullWidth
            multiline
            minRows={2}
          />
          <Box sx={{ display: "flex", gap: 1 }}>
            <Button
              variant="contained"
              size="small"
              onClick={addSection}
              disabled={!newName.trim() || !newDesc.trim()}
            >
              Adicionar
            </Button>
            <Button
              size="small"
              onClick={() => {
                setAdding(false);
                setNewName("");
                setNewDesc("");
              }}
            >
              Cancelar
            </Button>
          </Box>
        </Box>
      ) : (
        <Button
          startIcon={<AddIcon />}
          onClick={() => setAdding(true)}
          sx={{
            alignSelf: "flex-start",
            color: "rgba(255,255,255,0.5)",
            "&:hover": { color: "#7c3aed" },
          }}
        >
          Adicionar Seção
        </Button>
      )}
    </Paper>
  );
}
