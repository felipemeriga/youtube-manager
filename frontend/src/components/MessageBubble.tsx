import { useState, useEffect } from "react";
import { Box, TextField, Button, CircularProgress } from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import ReactMarkdown from "react-markdown";
import ApprovalButtons from "./ApprovalButtons";
import PhotoGrid from "./PhotoGrid";
import ScriptTopicList from "./ScriptTopicList";
import ScriptViewer from "./ScriptViewer";
import AssistantLogo from "./AssistantLogo";
import { supabase } from "../lib/supabase";

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
  onPhotoSelect?: (name: string, instructions?: string) => void;
  onSubmitText?: (text: string) => void;
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
  onPhotoSelect,
  onSubmitText,
  isLatest,
  isStreaming,
  conversationMode,
}: MessageBubbleProps) {
  void conversationMode;
  const isUser = message.role === "user";
  const showButtons = isLatest && !isStreaming && onApprove && onReject;
  const showImageButtons =
    showButtons &&
    (message.type === "image" ||
      message.type === "background" ||
      message.type === "composite");

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
            width: 30,
            height: 30,
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
          <AssistantLogo size={16} />
        </Box>
      )}

      <Box
        sx={{
          maxWidth: "70%",
          p: 2,
          borderRadius: 2.5,
          backgroundColor: isUser
            ? "rgba(124, 58, 237, 0.12)"
            : "rgba(23, 23, 32, 0.68)",
          backdropFilter: "blur(20px)",
          border: `1px solid ${
            isUser ? "rgba(124,58,237,0.2)" : "rgba(255,255,255,0.06)"
          }`,
          transition: "all 0.2s ease",
        }}
      >
        {(message.image_base64 || message.image_url) && (
          <AuthOutputImage
            base64={message.image_base64}
            storagePath={message.image_url || ""}
          />
        )}

        {message.type === "photo_grid" &&
          (() => {
            try {
              const photos = JSON.parse(message.content);
              return (
                <PhotoGrid
                  photos={photos}
                  onSelect={onPhotoSelect || (() => {})}
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

        {message.type === "text_prompt" && (
          isLatest && !isStreaming && onSubmitText ? (
            <TextPromptInput onSubmit={onSubmitText} />
          ) : (
            <Box sx={{ fontSize: 14, color: "rgba(255,255,255,0.5)" }}>
              {message.content}
            </Box>
          )
        )}

        {message.type === "topics" &&
          (() => {
            try {
              const topics = JSON.parse(message.content);
              return (
                <ScriptTopicList
                  topics={topics}
                  onSelect={onTopicSelect || (() => {})}
                  disabled={isStreaming}
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
          message.type !== "photo_grid" &&
          message.type !== "text_prompt" &&
          message.type !== "outline" &&
          message.type !== "script" &&
          message.type !== "research" && (
            <Box sx={{ fontSize: 14, lineHeight: 1.6, ...markdownStyles }}>
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </Box>
          )}

        {showImageButtons && (
          <ApprovalButtons
            onApprove={onApprove!}
            onReject={onReject!}
            variant={
              message.type === "background" || message.type === "composite"
                ? "step"
                : "thumbnail"
            }
          />
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

function AuthOutputImage({
  base64,
  storagePath,
}: {
  base64?: string;
  storagePath: string;
}) {
  const [src, setSrc] = useState<string | null>(
    base64 ? `data:image/png;base64,${base64}` : null
  );
  const [loading, setLoading] = useState(!base64);

  useEffect(() => {
    if (base64 || !storagePath) return;

    let revoke: string | null = null;
    const fetchImage = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session) return;

      // Extract filename from storage path (user-id/filename.png → filename.png)
      const filename = storagePath.includes("/")
        ? storagePath.split("/").pop()!
        : storagePath;

      const res = await fetch(`/api/assets/outputs/${filename}`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) {
        const blob = await res.blob();
        revoke = URL.createObjectURL(blob);
        setSrc(revoke);
      }
      setLoading(false);
    };
    fetchImage();

    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [base64, storagePath]);

  if (loading) {
    return (
      <Box
        sx={{
          width: "100%",
          maxWidth: 512,
          height: 200,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 1,
          mb: 1,
          backgroundColor: "rgba(255,255,255,0.03)",
        }}
      >
        <CircularProgress size={24} sx={{ color: "#7c3aed" }} />
      </Box>
    );
  }

  if (!src) return null;

  return (
    <Box
      component="img"
      src={src}
      alt="Thumbnail"
      sx={{
        width: "100%",
        maxWidth: 512,
        borderRadius: 1,
        mb: 1,
        display: "block",
      }}
    />
  );
}

function TextPromptInput({ onSubmit }: { onSubmit: (text: string) => void }) {
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setSubmitted(true);
    onSubmit(trimmed);
  };

  return (
    <Box sx={{ mt: 1.5 }}>
      <Box
        sx={{
          fontSize: 14,
          lineHeight: 1.6,
          color: "rgba(255,255,255,0.8)",
          mb: 1.5,
        }}
      >
        Qual texto você quer na thumbnail?
      </Box>
      <Box sx={{ display: "flex", gap: 1, alignItems: "flex-end" }}>
        <TextField
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder='ex: "Guerra do Irã e IA"'
          disabled={submitted}
          size="small"
          fullWidth
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              color: "#e2e8f0",
              backgroundColor: "rgba(0,0,0,0.2)",
              borderRadius: 2,
              "& fieldset": {
                borderColor: "rgba(124,58,237,0.3)",
              },
              "&:hover fieldset": {
                borderColor: "rgba(124,58,237,0.5)",
              },
              "&.Mui-focused fieldset": {
                borderColor: "#7c3aed",
              },
            },
            "& .MuiInputBase-input::placeholder": {
              color: "rgba(255,255,255,0.3)",
            },
          }}
        />
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={submitted || !text.trim()}
          sx={{
            backgroundColor: "#7c3aed",
            minWidth: 44,
            height: 40,
            "&:hover": { backgroundColor: "#6d28d9" },
            "&.Mui-disabled": {
              backgroundColor: "rgba(124,58,237,0.3)",
            },
          }}
        >
          <SendIcon sx={{ fontSize: 18 }} />
        </Button>
      </Box>
    </Box>
  );
}
