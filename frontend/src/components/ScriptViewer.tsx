import { Box } from "@mui/material";
import ReactMarkdown from "react-markdown";

interface ScriptViewerProps {
  content: string;
}

export default function ScriptViewer({ content }: ScriptViewerProps) {
  return (
    <Box
      sx={{
        mt: 1,
        p: 2,
        borderRadius: 1.5,
        backgroundColor: "rgba(0,0,0,0.2)",
        border: "1px solid rgba(255,255,255,0.06)",
        maxHeight: 500,
        overflow: "auto",
        fontSize: 14,
        lineHeight: 1.7,
      }}
    >
      <ReactMarkdown>{content}</ReactMarkdown>
    </Box>
  );
}
