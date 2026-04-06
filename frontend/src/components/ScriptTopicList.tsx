import { Box, Card, CardActionArea, CardContent, Typography, Chip } from "@mui/material";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";

interface Topic {
  title: string;
  angle: string;
  timeliness: string;
  interest: string;
}

interface ScriptTopicListProps {
  topics: Topic[];
  onSelect: (index: number) => void;
  disabled?: boolean;
}

const interestColors: Record<string, string> = {
  high: "#10b981",
  medium: "#f59e0b",
  low: "#6b7280",
};

export default function ScriptTopicList({
  topics,
  onSelect,
  disabled,
}: ScriptTopicListProps) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5, mt: 1 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
        Select a topic to develop:
      </Typography>
      {topics.map((topic, index) => (
        <Card
          key={index}
          sx={{
            backgroundColor: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.08)",
            "&:hover": {
              border: "1px solid rgba(124,58,237,0.4)",
              backgroundColor: "rgba(124,58,237,0.05)",
            },
          }}
        >
          <CardActionArea onClick={() => onSelect(index)} disabled={disabled}>
            <CardContent sx={{ py: 1.5, px: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                <TrendingUpIcon sx={{ fontSize: 16, color: "#7c3aed" }} />
                <Typography variant="subtitle2" sx={{ color: "rgba(255,255,255,0.95)" }}>
                  {topic.title}
                </Typography>
                <Chip
                  label={topic.interest}
                  size="small"
                  sx={{
                    ml: "auto",
                    height: 20,
                    fontSize: 11,
                    backgroundColor: `${interestColors[topic.interest] || "#6b7280"}22`,
                    color: interestColors[topic.interest] || "#6b7280",
                    border: `1px solid ${interestColors[topic.interest] || "#6b7280"}44`,
                  }}
                />
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: 13 }}>
                {topic.angle}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: 12, mt: 0.5, display: "block" }}>
                {topic.timeliness}
              </Typography>
            </CardContent>
          </CardActionArea>
        </Card>
      ))}
    </Box>
  );
}
