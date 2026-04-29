import { useRef, useEffect } from "react";
import { Box, Button, CircularProgress, Typography } from "@mui/material";
import MessageBubble from "./MessageBubble";
import AssistantLogo from "./AssistantLogo";
import ChatInput from "./ChatInput";
import ThinkingBar from "./ThinkingBar";

interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  type: string;
  image_url?: string | null;
  image_base64?: string;
  images?: Record<
    string,
    {
      preview_base64?: string;
      preview_url?: string;
      url?: string;
      base64?: string;
    }
  >;
}

interface ModelOption {
  id: string;
  label: string;
}

interface ChatAreaProps {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  currentStage: string | null;
  onSend: (content: string, imageUrl?: string) => void;
  onApprove: () => void;
  onReject: () => void;
  onTopicSelect?: (index: number) => void;
  onPhotoSelect?: (name: string, instructions?: string, compositeMode?: string, transformPrompt?: string) => void;
  onSkipPhoto?: () => void;
  onSubmitText?: (text: string) => void;
  conversationMode?: string;
  models?: ModelOption[];
  selectedModel?: string;
  onModelChange?: (model: string) => void;
  hasMoreMessages?: boolean;
  loadingMore?: boolean;
  onLoadMore?: () => void;
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
  onPhotoSelect,
  onSkipPhoto,
  onSubmitText,
  conversationMode,
  models,
  selectedModel,
  onModelChange,
  hasMoreMessages,
  loadingMore,
  onLoadMore,
}: ChatAreaProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, streamingContent]);

  const isEmpty = messages.length === 0 && !isStreaming;

  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        // leave room for the mobile hamburger button (top-left)
        pt: { xs: 5, md: 0 },
      }}
    >
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
              <AssistantLogo size={28} />
            </Box>
            <Typography variant="h6" color="text.secondary">
              {conversationMode === "script"
                ? "Descreva o vídeo que você quer criar"
                : "Descreva a thumbnail que você quer"}
            </Typography>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ maxWidth: 400, textAlign: "center" }}
            >
              {conversationMode === "script"
                ? "Conte sobre o tema ou peça sugestões de tendências..."
                : "Inclua o título do vídeo e preferências de estilo. O agente vai analisar suas referências e criar um plano."}
            </Typography>
          </Box>
        )}

        {hasMoreMessages && onLoadMore && (
          <Box sx={{ display: "flex", justifyContent: "center", mb: 2 }}>
            <Button
              variant="text"
              onClick={onLoadMore}
              disabled={loadingMore}
              size="small"
              sx={{
                color: "#c4b5fd",
                textTransform: "none",
                fontSize: 13,
              }}
            >
              {loadingMore ? (
                <CircularProgress size={14} sx={{ color: "#7c3aed", mr: 1 }} />
              ) : null}
              Carregar mensagens anteriores
            </Button>
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
            onPhotoSelect={onPhotoSelect}
            onSkipPhoto={onSkipPhoto}
            onSubmitText={onSubmitText}
            conversationMode={conversationMode}
          />
        ))}

        {isStreaming && streamingContent && (
          <MessageBubble
            message={{
              role: "assistant",
              content: streamingContent,
              type: "text",
            }}
            isStreaming={true}
          />
        )}
      </Box>

      {currentStage && <ThinkingBar stage={currentStage} />}

      <ChatInput
        onSend={onSend}
        disabled={isStreaming}
        models={models}
        selectedModel={selectedModel}
        onModelChange={onModelChange}
      />
    </Box>
  );
}
