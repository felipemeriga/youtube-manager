import { useState, useEffect, useRef, useCallback } from "react";
import {
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  Button,
  Stack,
  Typography,
} from "@mui/material";
import DescriptionIcon from "@mui/icons-material/Description";
import ImageIcon from "@mui/icons-material/Image";
import ContextPanel from "../components/ContextPanel";
import ChatArea from "../components/ChatArea";
import {
  listConversations,
  createConversation,
  getConversation,
  deleteConversation,
  streamChat,
  updateConversation,
  AVAILABLE_MODELS,
} from "../lib/api";

interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  type: string;
  image_url?: string | null;
  image_base64?: string;
}

interface Conversation {
  id: string;
  title: string | null;
  updated_at: string;
}

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [conversationMode, setConversationMode] = useState<string>("thumbnail");
  const [conversationModel, setConversationModel] = useState<string>("");
  const [showModeDialog, setShowModeDialog] = useState(false);
  const pendingMessageRef = useRef<{ content: string; type: string } | null>(
    null
  );
  const streamingRef = useRef("");
  const imageRef = useRef<{ base64: string; url: string } | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const loadConversations = useCallback(async () => {
    const data = await listConversations();
    setConversations(data as unknown as Conversation[]);
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleSelectConversation = async (id: string) => {
    stopPolling();
    setSelectedId(id);
    setCurrentStage(null);
    setIsStreaming(false);
    setStreamingContent("");

    try {
      const data = await getConversation(id);
      const convData = data as {
        messages: Message[];
        mode?: string;
        model?: string;
      };
      const msgs = convData.messages || [];
      const mode = convData.mode || "thumbnail";
      const model = convData.model || "";
      setMessages(msgs);
      setConversationMode(mode);
      setConversationModel(model);
    } catch {
      setMessages([]);
      setCurrentStage(null);
      setIsStreaming(false);
    }
  };

  const handleCreateConversation = () => {
    stopPolling();
    setCurrentStage(null);
    setIsStreaming(false);
    setStreamingContent("");
    setShowModeDialog(true);
  };

  const handleModeSelect = async (mode: string) => {
    setShowModeDialog(false);
    const conv = await createConversation(mode);
    const newConv = conv as unknown as Conversation;
    setConversations((prev) => [newConv, ...prev]);
    setSelectedId(newConv.id);
    setMessages([]);
    setConversationMode(mode);

    if (pendingMessageRef.current) {
      const { content, type } = pendingMessageRef.current;
      pendingMessageRef.current = null;
      await doStream(newConv.id, content, type);
    }
  };

  const handleDeleteConversation = async (id: string) => {
    await deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (selectedId === id) {
      setSelectedId(null);
      setMessages([]);
    }
  };

  const sendMessage = async (content: string, type: string = "text") => {
    if (!selectedId) {
      pendingMessageRef.current = { content, type };
      setShowModeDialog(true);
      return;
    }
    await doStream(selectedId, content, type);
  };

  const doStream = async (
    conversationId: string,
    content: string,
    type: string
  ) => {
    // Add user message to UI immediately
    if (type === "text") {
      setMessages((prev) => [...prev, { role: "user", content, type: "text" }]);
    }

    setIsStreaming(true);
    setStreamingContent("");
    streamingRef.current = "";
    imageRef.current = null;

    setCurrentStage("generating");

    try {
      await streamChat(conversationId, content, type, {
        onToken: (token) => {
          streamingRef.current += token;
          setStreamingContent(streamingRef.current);
        },
        onStage: (stage) => {
          setCurrentStage(stage);
        },
        onImage: (base64, url) => {
          imageRef.current = { base64, url };
        },
        onError: (error) => {
          const content = error.toLowerCase().includes("persona")
            ? `${error} [Go to Settings](/settings)`
            : `Error: ${error}`;
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content, type: "text" },
          ]);
          setStreamingContent("");
          setIsStreaming(false);
          setCurrentStage(null);
        },
        onDone: (data) => {
          const messageType = (data.message_type as string) || "text";
          const newMessage: Message = {
            role: "assistant",
            content: streamingRef.current || (data.content as string) || "",
            type: messageType,
          };
          if (imageRef.current) {
            newMessage.image_base64 = imageRef.current.base64;
            newMessage.image_url = imageRef.current.url;
          }
          if (data.saved) {
            const savedLabel =
              conversationMode === "script" ? "Script" : "Thumbnail";
            newMessage.content =
              (data.content as string) ||
              `${savedLabel} saved to ${(data.path as string) || "storage"}!`;
            newMessage.type = "text";
          }
          setMessages((prev) => [...prev, newMessage]);
          setStreamingContent("");
          setIsStreaming(false);
          setCurrentStage(null);
          loadConversations();
        },
      });
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Something went wrong. Please try again.",
          type: "text",
        },
      ]);
      setStreamingContent("");
      setIsStreaming(false);
      setCurrentStage(null);
    }
  };

  const handleSend = (content: string) => sendMessage(content, "text");

  const handleTopicSelect = (index: number) => {
    if (!selectedId) return;
    const topicsMsg = messages.find((m) => m.type === "topics");
    if (topicsMsg) {
      try {
        const topics = JSON.parse(topicsMsg.content);
        const topic = topics[index];
        const title = topic?.title || `Topic ${index + 1}`;
        sendMessage(`I want to make a video about: ${title}`);
      } catch {
        sendMessage(`I choose topic ${index + 1}`);
      }
    } else {
      sendMessage(`I choose topic ${index + 1}`);
    }
  };

  const handlePhotoSelect = (photoName: string, instructions?: string) => {
    if (!selectedId) return;
    const payload = JSON.stringify({
      action: "select_photo",
      photo_name: photoName,
      feedback: instructions || null,
    });
    doStream(selectedId, payload, "text");
  };

  const handleSubmitText = (text: string) => {
    if (!selectedId) return;
    doStream(
      selectedId,
      JSON.stringify({ action: "provide_text", text }),
      "text"
    );
  };

  const handleApprove = () => {
    if (!selectedId) return;
    doStream(selectedId, JSON.stringify({ action: "approve" }), "text");
  };

  const handleReject = () => {
    if (!selectedId) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.type === "script") {
      sendMessage("Please rewrite this script with improvements");
    } else {
      doStream(selectedId, JSON.stringify({ action: "feedback" }), "text");
    }
  };

  const handleModelChange = async (newModel: string) => {
    if (!selectedId) return;
    setConversationModel(newModel);
    await updateConversation(selectedId, { model: newModel || undefined });
  };

  return (
    <Box sx={{ display: "flex", flex: 1, overflow: "hidden" }}>
      <ContextPanel
        conversations={conversations}
        selectedId={selectedId}
        onSelect={handleSelectConversation}
        onCreate={handleCreateConversation}
        onDelete={handleDeleteConversation}
      />
      <ChatArea
        messages={messages}
        streamingContent={streamingContent}
        isStreaming={isStreaming}
        currentStage={currentStage}
        onSend={handleSend}
        onApprove={handleApprove}
        onReject={handleReject}
        onTopicSelect={handleTopicSelect}
        onPhotoSelect={handlePhotoSelect}
        onSubmitText={handleSubmitText}
        conversationMode={conversationMode}
        models={
          conversationMode === "script" && selectedId
            ? AVAILABLE_MODELS
            : undefined
        }
        selectedModel={conversationModel}
        onModelChange={
          conversationMode === "script" && selectedId
            ? handleModelChange
            : undefined
        }
      />
      <Dialog
        open={showModeDialog}
        onClose={() => setShowModeDialog(false)}
        PaperProps={{
          sx: {
            backgroundColor: "rgba(30,30,40,0.95)",
            backdropFilter: "blur(20px)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 3,
          },
        }}
      >
        <DialogTitle>New Conversation</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            What would you like to create?
          </Typography>
          <Stack spacing={1.5}>
            <Button
              variant="outlined"
              startIcon={<ImageIcon />}
              onClick={() => handleModeSelect("thumbnail")}
              sx={{
                justifyContent: "flex-start",
                borderColor: "rgba(255,255,255,0.15)",
                color: "text.primary",
                py: 1.5,
                "&:hover": {
                  borderColor: "#7c3aed",
                  backgroundColor: "rgba(124,58,237,0.08)",
                },
              }}
            >
              Thumbnail
            </Button>
            <Button
              variant="outlined"
              startIcon={<DescriptionIcon />}
              onClick={() => handleModeSelect("script")}
              sx={{
                justifyContent: "flex-start",
                borderColor: "rgba(255,255,255,0.15)",
                color: "text.primary",
                py: 1.5,
                "&:hover": {
                  borderColor: "#7c3aed",
                  backgroundColor: "rgba(124,58,237,0.08)",
                },
              }}
            >
              Video Script
            </Button>
          </Stack>
        </DialogContent>
      </Dialog>
    </Box>
  );
}
