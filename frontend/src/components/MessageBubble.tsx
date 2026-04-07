import { Box } from "@mui/material";
import ReactMarkdown from "react-markdown";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import ApprovalButtons from "./ApprovalButtons";
import ScriptTopicList from "./ScriptTopicList";
import ScriptViewer from "./ScriptViewer";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;

interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  type: string;
  image_url?: string | null;
  image_base64?: string;
}

interface MessageBubbleProps {
  message: Message;
  onApprove?: () => void;
  onReject?: () => void;
  onTopicSelect?: (index: number) => void;
  isLatest?: boolean;
  isStreaming?: boolean;
  conversationMode?: string;
}

const markdownStyles = {
  "& h1": {
    fontSize: 20,
    fontWeight: 700,
    mt: 2,
    mb: 1,
    color: "rgba(255,255,255,0.95)",
    "&:first-of-type": { mt: 0 },
  },
  "& h2": {
    fontSize: 17,
    fontWeight: 600,
    mt: 2,
    mb: 0.75,
    color: "rgba(255,255,255,0.9)",
    borderBottom: "1px solid rgba(255,255,255,0.1)",
    pb: 0.5,
  },
  "& h3": {
    fontSize: 15,
    fontWeight: 600,
    mt: 1.5,
    mb: 0.5,
    color: "#a78bfa",
  },
  "& p": {
    m: 0,
    mb: 1,
    lineHeight: 1.7,
    color: "rgba(255,255,255,0.8)",
    "&:last-child": { mb: 0 },
  },
  "& ul, & ol": {
    pl: 2.5,
    my: 0.75,
    "& li": {
      mb: 0.5,
      lineHeight: 1.6,
      color: "rgba(255,255,255,0.8)",
      "& p": { mb: 0 },
    },
  },
  "& strong": {
    color: "rgba(255,255,255,0.95)",
    fontWeight: 600,
  },
  "& em": {
    color: "rgba(255,255,255,0.7)",
    fontStyle: "italic",
  },
  "& code": {
    backgroundColor: "rgba(124,58,237,0.15)",
    border: "1px solid rgba(124,58,237,0.2)",
    borderRadius: 0.5,
    px: 0.75,
    py: 0.25,
    fontSize: 13,
    fontFamily: "monospace",
    color: "#c4b5fd",
  },
  "& pre": {
    backgroundColor: "rgba(0,0,0,0.3)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 1,
    p: 1.5,
    my: 1,
    overflow: "auto",
    "& code": {
      backgroundColor: "transparent",
      border: "none",
      p: 0,
      color: "rgba(255,255,255,0.85)",
    },
  },
  "& hr": {
    border: "none",
    borderTop: "1px solid rgba(255,255,255,0.1)",
    my: 2,
  },
  "& table": {
    width: "100%",
    borderCollapse: "collapse",
    my: 1,
    fontSize: 13,
    "& th": {
      textAlign: "left",
      p: 0.75,
      borderBottom: "1px solid rgba(255,255,255,0.15)",
      color: "rgba(255,255,255,0.9)",
      fontWeight: 600,
    },
    "& td": {
      p: 0.75,
      borderBottom: "1px solid rgba(255,255,255,0.06)",
      color: "rgba(255,255,255,0.7)",
    },
  },
  "& blockquote": {
    borderLeft: "3px solid #7c3aed",
    pl: 1.5,
    ml: 0,
    my: 1,
    color: "rgba(255,255,255,0.6)",
    fontStyle: "italic",
  },
};

export default function MessageBubble({
  message,
  onApprove,
  onReject,
  onTopicSelect,
  isLatest,
  isStreaming,
  conversationMode,
}: MessageBubbleProps) {
  void conversationMode;
  const isUser = message.role === "user";
  const showButtons = isLatest && !isStreaming && onApprove && onReject;

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        px: 3,
        py: 0.75,
      }}
    >
      {!isUser && (
        <Box
          sx={{
            width: 28,
            height: 28,
            borderRadius: "50%",
            background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            mr: 1,
            mt: 0.5,
            flexShrink: 0,
          }}
        >
          <AutoAwesomeIcon sx={{ fontSize: 14, color: "#fff" }} />
        </Box>
      )}

      <Box
        sx={{
          maxWidth: "70%",
          p: 2,
          borderRadius: 2,
          backgroundColor: isUser
            ? "rgba(124, 58, 237, 0.15)"
            : "rgba(255, 255, 255, 0.05)",
          backdropFilter: "blur(10px)",
          border: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        {(message.image_base64 || message.image_url) && (
          <Box
            component="img"
            src={
              message.image_base64
                ? `data:image/png;base64,${message.image_base64}`
                : `${SUPABASE_URL}/storage/v1/object/public/outputs/${message.image_url}`
            }
            alt="Generated thumbnail"
            sx={{
              width: "100%",
              maxWidth: 512,
              borderRadius: 1,
              mb: 1,
              display: "block",
            }}
          />
        )}

        {message.type === "topics" &&
          (() => {
            try {
              const topics = JSON.parse(message.content);
              return (
                <ScriptTopicList
                  topics={topics}
                  onSelect={onTopicSelect || (() => {})}
                  disabled={!isLatest || isStreaming}
                />
              );
            } catch {
              return (
                <Box sx={{ fontSize: 14, lineHeight: 1.6, ...markdownStyles }}>
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </Box>
              );
            }
          })()}

        {(message.type === "outline" ||
          message.type === "script" ||
          message.type === "research") && (
          <ScriptViewer content={message.content} />
        )}

        {message.type !== "topics" &&
          message.type !== "outline" &&
          message.type !== "script" &&
          message.type !== "research" && (
            <Box sx={{ fontSize: 14, lineHeight: 1.6, ...markdownStyles }}>
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </Box>
          )}

        {showButtons && message.type === "image" && (
          <ApprovalButtons onApprove={onApprove} onReject={onReject} />
        )}

        {showButtons && message.type === "script" && (
          <ApprovalButtons
            onApprove={onApprove!}
            onReject={onReject!}
            variant="script"
          />
        )}
      </Box>
    </Box>
  );
}
