import { Box } from "@mui/material";
import ReactMarkdown from "react-markdown";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import ApprovalButtons from "./ApprovalButtons";

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
  isLatest?: boolean;
  isStreaming?: boolean;
}

export default function MessageBubble({
  message,
  onApprove,
  onReject,
  isLatest,
  isStreaming,
}: MessageBubbleProps) {
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
        {message.image_base64 && (
          <Box
            component="img"
            src={`data:image/png;base64,${message.image_base64}`}
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

        <Box sx={{ "& p": { m: 0 }, "& p + p": { mt: 1 }, fontSize: 14, lineHeight: 1.6 }}>
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </Box>

        {showButtons && message.type === "plan" && (
          <ApprovalButtons type="plan" onApprove={onApprove} onReject={onReject} />
        )}
        {showButtons && message.type === "image" && (
          <ApprovalButtons type="image" onApprove={onApprove} onReject={onReject} />
        )}
      </Box>
    </Box>
  );
}
