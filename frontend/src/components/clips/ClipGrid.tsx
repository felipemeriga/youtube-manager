import { Box } from "@mui/material";
import type { ClipCandidate } from "../../types/clips";
import ClipCard from "./ClipCard";

export default function ClipGrid({
  candidates, selected, onToggleSelect, onClickCard,
}: {
  candidates: ClipCandidate[];
  selected: Set<string>;
  onToggleSelect: (id: string) => void;
  onClickCard: (c: ClipCandidate) => void;
}) {
  return (
    <Box sx={{
      display: "grid", gap: 2,
      gridTemplateColumns: {
        xs: "1fr",
        sm: "repeat(2, 1fr)",
        md: "repeat(3, 1fr)",
        lg: "repeat(4, 1fr)",
      },
    }}>
      {candidates.map(c => (
        <ClipCard
          key={c.id}
          candidate={c}
          selected={selected.has(c.id)}
          onToggleSelect={() => onToggleSelect(c.id)}
          onClick={() => onClickCard(c)}
        />
      ))}
    </Box>
  );
}
