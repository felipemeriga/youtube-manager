import { useState, useEffect, useRef, useCallback } from "react";
import {
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  Button,
  Stack,
  Typography,
  Checkbox,
  FormControlLabel,
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
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([
    "youtube",
  ]);
  const [qualityTier, setQualityTier] = useState("balanced");
  const pendingMessageRef = useRef<{
    content: string;
    type: string;
    imageUrl?: string;
    platforms?: string[];
  } | null>(null);
  const streamingRef = useRef("");
  const imageRef = useRef<{ base64: string; url: string } | null>(null);
  const imagesRef = useRef<Record<
    string,
    { base64?: string; url?: string }
  > | null>(null);

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
      const { content, type, imageUrl, platforms } = pendingMessageRef.current;
      pendingMessageRef.current = null;
      await doStream(
        newConv.id,
        content,
        type,
        imageUrl,
        mode === "thumbnail" ? platforms : undefined,
        mode === "thumbnail" ? qualityTier : undefined
      );
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

  const sendMessage = async (
    content: string,
    type: string = "text",
    imageUrl?: string,
    platforms?: string[]
  ) => {
    if (!selectedId) {
      pendingMessageRef.current = { content, type, imageUrl, platforms };
      setShowModeDialog(true);
      return;
    }
    await doStream(
      selectedId,
      content,
      type,
      imageUrl,
      platforms,
      conversationMode === "thumbnail" ? qualityTier : undefined
    );
  };

  const doStream = async (
    conversationId: string,
    content: string,
    type: string,
    imageUrl?: string,
    platforms?: string[],
    tier?: string
  ) => {
    // Add user message to UI immediately with readable label
    if (type === "text") {
      let displayContent = content;
      try {
        const parsed = JSON.parse(content);
        if (parsed?.action === "approve") displayContent = "Aprovado ✓";
        else if (parsed?.action === "feedback")
          displayContent = parsed.feedback || "Refazer";
        else if (parsed?.action === "select_photo") {
          displayContent = parsed.feedback
            ? `Selecionado: ${parsed.photo_name} — "${parsed.feedback}"`
            : `Selecionado: ${parsed.photo_name}`;
        } else if (parsed?.action === "provide_text")
          displayContent = `Texto: "${parsed.text}"`;
        else if (parsed?.action === "save") displayContent = "Salvar";
      } catch {
        // Not JSON — use content as-is
      }
      const userMsg: Message = {
        role: "user",
        content: displayContent,
        type: "text",
      };
      if (imageUrl) {
        userMsg.image_url = imageUrl;
      }
      setMessages((prev) => [...prev, userMsg]);
    }

    setIsStreaming(true);
    setStreamingContent("");
    streamingRef.current = "";
    imageRef.current = null;
    imagesRef.current = null;

    setCurrentStage("generating");

    try {
      await streamChat(
        conversationId,
        content,
        type,
        {
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
          onImages: (imgs) => {
            imagesRef.current = imgs;
          },
          onError: (error) => {
            const content = error.toLowerCase().includes("persona")
              ? `${error} [Ir para Configurações](/settings)`
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
            if (imagesRef.current) {
              newMessage.images = imagesRef.current;
              // Also set backward-compat fields from first platform image
              const firstImg = Object.values(imagesRef.current)[0];
              if (firstImg) {
                newMessage.image_base64 = firstImg.base64;
                newMessage.image_url = firstImg.url;
              }
            } else if (imageRef.current) {
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
        },
        imageUrl,
        platforms,
        tier
      );
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Algo deu errado. Tente novamente.",
          type: "text",
        },
      ]);
      setStreamingContent("");
      setIsStreaming(false);
      setCurrentStage(null);
    }
  };

  const handleSend = (content: string, imageUrl?: string) =>
    sendMessage(
      content,
      "text",
      imageUrl,
      conversationMode === "thumbnail" ? selectedPlatforms : undefined
    );

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
      sendMessage("Reescreva o roteiro com melhorias");
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
        qualityTier={qualityTier}
        onQualityTierChange={setQualityTier}
        showQualityTier={conversationMode === "thumbnail"}
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
        <DialogTitle>Nova Conversa</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            O que você quer criar?
          </Typography>
          <Stack spacing={1.5}>
            <Box>
              <Button
                variant="outlined"
                startIcon={<ImageIcon />}
                onClick={() => handleModeSelect("thumbnail")}
                sx={{
                  justifyContent: "flex-start",
                  borderColor: "rgba(255,255,255,0.15)",
                  color: "text.primary",
                  py: 1.5,
                  width: "100%",
                  "&:hover": {
                    borderColor: "#7c3aed",
                    backgroundColor: "rgba(124,58,237,0.08)",
                  },
                }}
              >
                Thumbnail
              </Button>
              <Box sx={{ ml: 4, mt: 1 }}>
                {[
                  { key: "youtube", label: "YouTube (16:9)" },
                  { key: "instagram_post", label: "Instagram Post (1:1)" },
                  { key: "instagram_story", label: "Instagram Story (9:16)" },
                ].map((p) => (
                  <FormControlLabel
                    key={p.key}
                    control={
                      <Checkbox
                        checked={selectedPlatforms.includes(p.key)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedPlatforms((prev) => [...prev, p.key]);
                          } else {
                            setSelectedPlatforms((prev) =>
                              prev.filter((k) => k !== p.key)
                            );
                          }
                        }}
                        size="small"
                        sx={{
                          color: "#7c3aed",
                          "&.Mui-checked": { color: "#7c3aed" },
                        }}
                      />
                    }
                    label={p.label}
                    sx={{
                      color: "rgba(255,255,255,0.7)",
                      display: "flex",
                      "& .MuiTypography-root": { fontSize: 13 },
                    }}
                  />
                ))}
              </Box>
            </Box>
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
              Roteiro de Vídeo
            </Button>
          </Stack>
        </DialogContent>
      </Dialog>
    </Box>
  );
}
