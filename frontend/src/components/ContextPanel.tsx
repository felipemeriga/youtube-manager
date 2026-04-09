import {
  Box,
  Typography,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DescriptionIcon from "@mui/icons-material/Description";
import ImageIcon from "@mui/icons-material/Image";
import { useState } from "react";

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
}

export default function ContextPanel({
  conversations,
  selectedId,
  onSelect,
  onCreate,
  onDelete,
}: ContextPanelProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  return (
    <Box
      sx={{
        width: 220,
        borderRight: "1px solid rgba(255,255,255,0.06)",
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
          Conversations
        </Typography>
        <IconButton
          size="small"
          onClick={onCreate}
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

      <List sx={{ flex: 1, overflow: "auto", px: 0.75, py: 0.75 }}>
        {conversations.map((conv) => (
          <ListItemButton
            key={conv.id}
            selected={conv.id === selectedId}
            onClick={() => onSelect(conv.id)}
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
                primary={conv.title || "New conversation"}
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
                  {conv.mode === "script" ? "Script" : "Thumb"}
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
