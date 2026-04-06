import { useState, useEffect, useRef, useCallback } from "react";
import { Box } from "@mui/material";
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
  const streamingRef = useRef("");
  const imageRef = useRef<{ base64: string; url: string } | null>(null);

  const loadConversations = useCallback(async () => {
    const data = await listConversations();
    setConversations(data as unknown as Conversation[]);
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleSelectConversation = async (id: string) => {
    setSelectedId(id);
    const data = await getConversation(id);
    setMessages((data as { messages: Message[] }).messages || []);
  };

  const handleCreateConversation = async () => {
    const conv = await createConversation();
    const newConv = conv as unknown as Conversation;
    setConversations((prev) => [newConv, ...prev]);
    setSelectedId(newConv.id);
    setMessages([]);
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
      // Auto-create conversation
      const conv = await createConversation();
      const newConv = conv as unknown as Conversation;
      setConversations((prev) => [newConv, ...prev]);
      setSelectedId(newConv.id);
      await doStream(newConv.id, content, type);
    } else {
      await doStream(selectedId, content, type);
    }
  };

  const doStream = async (conversationId: string, content: string, type: string) => {
    // Add user message to UI immediately
    if (type === "text") {
      setMessages((prev) => [...prev, { role: "user", content, type: "text" }]);
    }

    setIsStreaming(true);
    setStreamingContent("");
    setCurrentStage(null);
    streamingRef.current = "";
    imageRef.current = null;

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
          newMessage.content = data.content as string || "Thumbnail saved!";
          newMessage.type = "text";
        }
        setMessages((prev) => [...prev, newMessage]);
        setStreamingContent("");
        setIsStreaming(false);
        setCurrentStage(null);
        loadConversations();
      },
    });
  };

  const handleSend = (content: string) => sendMessage(content, "text");

  const handleApprove = () => {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.type === "plan") {
      sendMessage("APPROVED", "approval");
    } else if (lastMsg?.type === "image") {
      sendMessage("SAVE_OUTPUT", "save");
    }
  };

  const handleReject = () => {
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.type === "plan") {
      // Let user type feedback — just focus the input
    } else if (lastMsg?.type === "image") {
      sendMessage("REGENERATE", "regenerate");
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
      />
    </Box>
  );
}
