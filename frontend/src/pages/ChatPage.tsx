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

  const detectPendingStage = (msgs: Message[], mode: string): string | null => {
    if (mode !== "script" || msgs.length === 0) return null;
    const lastMsg = msgs[msgs.length - 1];
    if (lastMsg.role !== "user") return null;

    if (lastMsg.type === "text") return "finding_trends";
    if (lastMsg.type === "topic_selection") return "researching";
    if (lastMsg.type === "approval") {
      const lastAssistant = [...msgs]
        .reverse()
        .find((m) => m.role === "assistant");
      if (lastAssistant?.type === "outline") return "writing_script";
      if (lastAssistant?.type === "script") return "saving";
    }
    return null;
  };

  const startPolling = useCallback(
    (convId: string, initialCount: number) => {
      stopPolling();
      let attempts = 0;
      const maxAttempts = 60; // ~5 minutes at 5s intervals

      pollRef.current = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts) {
          stopPolling();
          setCurrentStage(null);
          setIsStreaming(false);
          return;
        }
        try {
          const data = await getConversation(convId);
          const convData = data as { messages: Message[]; mode?: string };
          const newMsgs = convData.messages || [];
          if (newMsgs.length > initialCount) {
            setMessages(newMsgs);
            stopPolling();
            setCurrentStage(null);
            setIsStreaming(false);
          }
        } catch {
          // ignore poll errors
        }
      }, 5000);
    },
    [stopPolling]
  );

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

    const data = await getConversation(id);
    const convData = data as { messages: Message[]; mode?: string };
    const msgs = convData.messages || [];
    const mode = convData.mode || "thumbnail";
    setMessages(msgs);
    setConversationMode(mode);

    const pendingStage = detectPendingStage(msgs, mode);
    if (pendingStage) {
      setCurrentStage(pendingStage);
      setIsStreaming(true);
      startPolling(id, msgs.length);
    }
  };

  const handleCreateConversation = () => {
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
    setCurrentStage(null);
    streamingRef.current = "";
    imageRef.current = null;

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
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `Error: ${error}`, type: "text" },
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
            newMessage.content = (data.content as string) || "Thumbnail saved!";
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
    doStream(selectedId, String(index), "topic_selection");
  };

  const handleApprove = () => {
    if (!selectedId) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.type === "image") {
      sendMessage("SAVE_OUTPUT", "save");
    } else if (lastMsg?.type === "outline") {
      doStream(selectedId, "", "approve_outline");
    } else if (lastMsg?.type === "script") {
      doStream(selectedId, "", "approve_script");
    }
  };

  const handleReject = () => {
    if (!selectedId) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.type === "image") {
      sendMessage("REGENERATE", "regenerate");
    } else if (lastMsg?.type === "outline") {
      doStream(selectedId, "", "reject_outline");
    } else if (lastMsg?.type === "script") {
      doStream(selectedId, "", "reject_script");
    }
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
        conversationMode={conversationMode}
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
