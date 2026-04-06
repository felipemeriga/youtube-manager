import { useRef, useEffect } from "react";
import { Box, Typography } from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import ThinkingBar from "./ThinkingBar";

interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  type: string;
  image_url?: string | null;
  image_base64?: string;
}

interface ChatAreaProps {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  currentStage: string | null;
  onSend: (content: string) => void;
  onApprove: () => void;
  onReject: () => void;
  onTopicSelect?: (index: number) => void;
  conversationMode?: string;
}

export default function ChatArea({
  messages,
  streamingContent,
  isStreaming,
  currentStage,
  onSend,
  onApprove,
  onReject,
  onTopicSelect,
  conversationMode,
}: ChatAreaProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streamingContent]);

  const isEmpty = messages.length === 0 && !isStreaming;

  return (
    <Box sx={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Box ref={scrollRef} sx={{ flex: 1, overflow: "auto", py: 2 }}>
        {isEmpty && (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              gap: 2,
            }}
          >
            <Box
              sx={{
                width: 56,
                height: 56,
                borderRadius: "50%",
                background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <AutoAwesomeIcon sx={{ color: "#fff", fontSize: 28 }} />
            </Box>
            <Typography variant="h6" color="text.secondary">
              {conversationMode === "script"
                ? "Describe the video you want to create"
                : "Describe the thumbnail you want"}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 400, textAlign: "center" }}>
              {conversationMode === "script"
                ? "Tell me about the topic or ask for trending suggestions..."
                : "Include the video title and any style preferences. The agent will analyze your references and create a plan."}
            </Typography>
          </Box>
        )}

        {messages.map((msg, i) => (
          <MessageBubble
            key={msg.id || i}
            message={msg}
            isLatest={i === messages.length - 1 && !isStreaming}
            isStreaming={false}
            onApprove={onApprove}
            onReject={onReject}
            onTopicSelect={onTopicSelect}
            conversationMode={conversationMode}
          />
        ))}

        {isStreaming && streamingContent && (
          <MessageBubble
            message={{ role: "assistant", content: streamingContent, type: "text" }}
            isStreaming={true}
          />
        )}
      </Box>

      {currentStage && <ThinkingBar stage={currentStage} />}

      <ChatInput onSend={onSend} disabled={isStreaming} />
    </Box>
  );
}
