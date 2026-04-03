import { Box, Typography, IconButton, List, ListItemButton, ListItemText } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { useState } from "react";

interface Conversation {
  id: string;
  title: string | null;
  updated_at: string;
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
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", p: 1.5 }}>
        <Typography variant="subtitle2" color="text.secondary">
          Conversations
        </Typography>
        <IconButton size="small" onClick={onCreate} sx={{ color: "rgba(255,255,255,0.5)" }}>
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
            <ListItemText
              primary={conv.title || "New conversation"}
              primaryTypographyProps={{
                noWrap: true,
                fontSize: 13,
                color: "text.primary",
              }}
            />
            {hoveredId === conv.id && (
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(conv.id);
                }}
                sx={{ color: "rgba(255,255,255,0.3)", "&:hover": { color: "#ef4444" } }}
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
