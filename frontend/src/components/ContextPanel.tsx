import {
  Box,
  Typography,
  IconButton,
  InputBase,
  List,
  ListItemButton,
  ListItemText,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DescriptionIcon from "@mui/icons-material/Description";
import ImageIcon from "@mui/icons-material/Image";
import SearchIcon from "@mui/icons-material/Search";
import ClearIcon from "@mui/icons-material/Clear";
import { useMemo, useState } from "react";

interface Conversation {
  id: string;
  title: string | null;
  updated_at: string;
  mode?: string;
}

interface ContextPanelProps {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
  /** Called after a navigation action so the parent can close a mobile drawer. */
  onAfterNavigate?: () => void;
}

export default function ContextPanel({
  conversations,
  selectedId,
  onSelect,
  onCreate,
  onDelete,
  onAfterNavigate,
}: ContextPanelProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((c) =>
      (c.title ?? "Nova conversa").toLowerCase().includes(q)
    );
  }, [conversations, query]);

  return (
    <Box
      sx={{
        width: { xs: "100%", md: 220 },
        height: "100%",
        borderRight: { xs: "none", md: "1px solid rgba(255,255,255,0.06)" },
        backgroundColor: "rgba(18, 18, 25, 0.95)",
        backdropFilter: "blur(16px)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          p: 1.5,
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <Typography
          variant="subtitle2"
          sx={{
            color: "rgba(255,255,255,0.5)",
            fontWeight: 600,
            letterSpacing: "0.02em",
          }}
        >
          Conversas
        </Typography>
        <IconButton
          size="small"
          onClick={() => {
            onCreate();
            onAfterNavigate?.();
          }}
          sx={{
            color: "rgba(255,255,255,0.4)",
            "&:hover": {
              color: "#a78bfa",
              backgroundColor: "rgba(124,58,237,0.08)",
            },
            transition: "all 0.2s ease",
          }}
        >
          <AddIcon fontSize="small" />
        </IconButton>
      </Box>

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 0.5,
          mx: 1,
          mt: 1,
          mb: 0.5,
          px: 1,
          py: 0.5,
          borderRadius: 1.5,
          backgroundColor: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.06)",
          "&:focus-within": {
            borderColor: "rgba(124,58,237,0.5)",
            backgroundColor: "rgba(255,255,255,0.05)",
          },
        }}
      >
        <SearchIcon sx={{ fontSize: 16, color: "rgba(255,255,255,0.35)" }} />
        <InputBase
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar..."
          sx={{
            flex: 1,
            color: "rgba(255,255,255,0.85)",
            fontSize: 12,
            "& input::placeholder": { color: "rgba(255,255,255,0.3)", opacity: 1 },
          }}
        />
        {query && (
          <IconButton
            size="small"
            onClick={() => setQuery("")}
            sx={{
              p: 0.25,
              color: "rgba(255,255,255,0.35)",
              "&:hover": { color: "rgba(255,255,255,0.7)" },
            }}
          >
            <ClearIcon sx={{ fontSize: 14 }} />
          </IconButton>
        )}
      </Box>

      <List sx={{ flex: 1, overflow: "auto", px: 0.75, py: 0.75 }}>
        {filtered.length === 0 && query && (
          <Typography
            variant="caption"
            sx={{
              display: "block",
              textAlign: "center",
              color: "rgba(255,255,255,0.35)",
              py: 2,
            }}
          >
            Nenhuma conversa encontrada
          </Typography>
        )}
        {conversations.length === 0 && !query && (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 1,
              px: 2,
              py: 4,
              textAlign: "center",
            }}
          >
            <Typography
              variant="caption"
              sx={{ color: "rgba(255,255,255,0.5)", fontWeight: 600 }}
            >
              Nenhuma conversa ainda
            </Typography>
            <Typography
              variant="caption"
              sx={{ color: "rgba(255,255,255,0.35)", lineHeight: 1.4 }}
            >
              Clique em + acima para criar sua primeira thumbnail ou roteiro.
            </Typography>
          </Box>
        )}
        {filtered.map((conv) => (
          <ListItemButton
            key={conv.id}
            selected={conv.id === selectedId}
            onClick={() => {
              onSelect(conv.id);
              onAfterNavigate?.();
            }}
            onMouseEnter={() => setHoveredId(conv.id)}
            onMouseLeave={() => setHoveredId(null)}
            sx={{
              borderRadius: 1.5,
              mb: 0.5,
              py: 0.75,
              transition: "all 0.2s ease",
              "&.Mui-selected": {
                backgroundColor: "rgba(124, 58, 237, 0.12)",
                "&:hover": { backgroundColor: "rgba(124, 58, 237, 0.18)" },
              },
              "&:hover": { backgroundColor: "rgba(255,255,255,0.04)" },
            }}
          >
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                gap: 0.5,
                flex: 1,
                minWidth: 0,
              }}
            >
              <ListItemText
                primary={conv.title || "Nova conversa"}
                primaryTypographyProps={{
                  noWrap: true,
                  fontSize: 13,
                  fontWeight: conv.id === selectedId ? 500 : 400,
                  color:
                    conv.id === selectedId
                      ? "rgba(255,255,255,0.95)"
                      : "rgba(255,255,255,0.7)",
                }}
                sx={{ m: 0 }}
              />
              <Box
                sx={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 0.5,
                  px: 0.75,
                  py: 0.15,
                  borderRadius: 0.75,
                  backgroundColor:
                    conv.mode === "script"
                      ? "rgba(59,130,246,0.1)"
                      : "rgba(124,58,237,0.1)",
                  border: `1px solid ${
                    conv.mode === "script"
                      ? "rgba(59,130,246,0.2)"
                      : "rgba(124,58,237,0.2)"
                  }`,
                  width: "fit-content",
                }}
              >
                {conv.mode === "script" ? (
                  <DescriptionIcon sx={{ fontSize: 11, color: "#60a5fa" }} />
                ) : (
                  <ImageIcon sx={{ fontSize: 11, color: "#a78bfa" }} />
                )}
                <Typography
                  sx={{
                    fontSize: 10,
                    fontWeight: 600,
                    color: conv.mode === "script" ? "#60a5fa" : "#a78bfa",
                    textTransform: "uppercase",
                    letterSpacing: 0.5,
                  }}
                >
                  {conv.mode === "script" ? "Roteiro" : "Thumb"}
                </Typography>
              </Box>
            </Box>
            {hoveredId === conv.id && (
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(conv.id);
                }}
                sx={{
                  color: "rgba(255,255,255,0.3)",
                  "&:hover": { color: "#ef4444" },
                  transition: "all 0.2s ease",
                }}
              >
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            )}
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
}
