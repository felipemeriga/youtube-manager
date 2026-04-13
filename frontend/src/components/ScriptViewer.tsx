import { Box } from "@mui/material";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ScriptViewerProps {
  content: string;
}

export default function ScriptViewer({ content }: ScriptViewerProps) {
  return (
    <Box
      sx={{
        mt: 1,
        p: 3,
        borderRadius: 2,
        backgroundColor: "rgba(0,0,0,0.25)",
        border: "1px solid rgba(255,255,255,0.06)",
        maxHeight: 600,
        overflow: "auto",
        fontSize: 14,
        lineHeight: 1.8,
        "& h1": {
          fontSize: "1.6rem",
          fontWeight: 700,
          mt: 0,
          mb: 2,
          pb: 1.5,
          borderBottom: "1px solid rgba(255,255,255,0.1)",
        },
        "& h2": {
          fontSize: "1.2rem",
          fontWeight: 600,
          mt: 3,
          mb: 1.5,
          pb: 1,
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          color: "#c4b5fd",
        },
        "& h3": {
          fontSize: "1rem",
          fontWeight: 600,
          mt: 2.5,
          mb: 1,
          color: "#93c5fd",
        },
        "& p": {
          mb: 1.5,
          color: "rgba(255,255,255,0.85)",
        },
        "& a": {
          color: "#7c3aed",
          textDecoration: "none",
          borderBottom: "1px solid rgba(124,58,237,0.3)",
          transition: "all 0.15s",
          "&:hover": {
            color: "#a78bfa",
            borderBottomColor: "#a78bfa",
          },
        },
        "& table": {
          width: "100%",
          borderCollapse: "collapse",
          my: 2,
          fontSize: "0.8rem",
        },
        "& thead": {
          backgroundColor: "rgba(124,58,237,0.1)",
        },
        "& th": {
          textAlign: "left",
          px: 1.5,
          py: 1,
          fontWeight: 600,
          borderBottom: "2px solid rgba(124,58,237,0.3)",
          color: "#c4b5fd",
          whiteSpace: "nowrap",
        },
        "& td": {
          px: 1.5,
          py: 1,
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          color: "rgba(255,255,255,0.75)",
        },
        "& tr:hover td": {
          backgroundColor: "rgba(255,255,255,0.02)",
        },
        "& blockquote": {
          borderLeft: "3px solid #7c3aed",
          ml: 0,
          pl: 2,
          py: 0.5,
          my: 1.5,
          backgroundColor: "rgba(124,58,237,0.05)",
          borderRadius: "0 8px 8px 0",
          "& p": {
            mb: 0.5,
          },
        },
        "& ol, & ul": {
          pl: 3,
          mb: 2,
          "& li": {
            mb: 1,
            color: "rgba(255,255,255,0.85)",
          },
        },
        "& hr": {
          border: "none",
          borderTop: "1px solid rgba(255,255,255,0.08)",
          my: 3,
        },
        "& strong": {
          color: "rgba(255,255,255,0.95)",
          fontWeight: 600,
        },
        "& em": {
          color: "rgba(255,255,255,0.6)",
          fontStyle: "italic",
        },
        "& code": {
          backgroundColor: "rgba(255,255,255,0.06)",
          px: 0.75,
          py: 0.25,
          borderRadius: 0.5,
          fontSize: "0.85em",
        },
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </Box>
  );
}
