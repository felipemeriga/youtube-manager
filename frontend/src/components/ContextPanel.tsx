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
        borderRight: "1px solid rgba(255,255,255,0.08)",
        backgroundColor: "rgba(0,0,0,0.2)",
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
        }}
      >
        <Typography variant="subtitle2" color="text.secondary">
          Conversations
        </Typography>
        <IconButton
          size="small"
          onClick={onCreate}
          sx={{ color: "rgba(255,255,255,0.5)" }}
        >
          <AddIcon fontSize="small" />
        </IconButton>
      </Box>

      <List sx={{ flex: 1, overflow: "auto", px: 0.5 }}>
        {conversations.map((conv) => (
          <ListItemButton
            key={conv.id}
            selected={conv.id === selectedId}
            onClick={() => onSelect(conv.id)}
            onMouseEnter={() => setHoveredId(conv.id)}
            onMouseLeave={() => setHoveredId(null)}
            sx={{
              borderRadius: 1,
              mb: 0.5,
              py: 0.75,
              "&.Mui-selected": {
                backgroundColor: "rgba(124, 58, 237, 0.15)",
              },
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
                  color: "text.primary",
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
                      ? "rgba(59,130,246,0.15)"
                      : "rgba(124,58,237,0.15)",
                  border: `1px solid ${
                    conv.mode === "script"
                      ? "rgba(59,130,246,0.3)"
                      : "rgba(124,58,237,0.3)"
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
