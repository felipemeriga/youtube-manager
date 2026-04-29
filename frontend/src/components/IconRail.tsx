import { Box, IconButton, Tooltip, Avatar } from "@mui/material";
import ChatIcon from "@mui/icons-material/Chat";
import PhotoLibraryIcon from "@mui/icons-material/PhotoLibrary";
import VideoLibraryIcon from "@mui/icons-material/VideoLibrary";
import LogoutIcon from "@mui/icons-material/Logout";
import SettingsIcon from "@mui/icons-material/Settings";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";

export default function IconRail() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signOut, user } = useAuth();

  const isActive = (path: string) => location.pathname === path;

  const initial = user?.email?.[0]?.toUpperCase() || "?";

  return (
    <Box
      sx={{
        width: 52,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        py: 2,
        gap: 1,
        borderRight: "1px solid rgba(255,255,255,0.06)",
        backgroundColor: "#0c0c12",
      }}
    >
      <Box
        component="img"
        src="/logo.svg"
        alt="YouTube Manager"
        sx={{ width: 30, height: 30, mb: 2, borderRadius: 1 }}
      />

      <Tooltip title="Chat" placement="right">
        <IconButton
          onClick={() => navigate("/")}
          sx={{
            color: isActive("/") ? "#a78bfa" : "rgba(255,255,255,0.4)",
            backgroundColor: isActive("/")
              ? "rgba(124,58,237,0.12)"
              : "transparent",
            "&:hover": {
              color: "#a78bfa",
              backgroundColor: "rgba(124,58,237,0.08)",
            },
            transition: "all 0.2s ease",
          }}
        >
          <ChatIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <Tooltip title="Arquivos" placement="right">
        <IconButton
          onClick={() => navigate("/assets")}
          sx={{
            color: isActive("/assets") ? "#a78bfa" : "rgba(255,255,255,0.4)",
            backgroundColor: isActive("/assets")
              ? "rgba(124,58,237,0.12)"
              : "transparent",
            "&:hover": {
              color: "#a78bfa",
              backgroundColor: "rgba(124,58,237,0.08)",
            },
            transition: "all 0.2s ease",
          }}
        >
          <PhotoLibraryIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <Tooltip title="Clips" placement="right">
        <IconButton
          onClick={() => navigate("/clips")}
          sx={{
            color: location.pathname.startsWith("/clips")
              ? "#a78bfa"
              : "rgba(255,255,255,0.4)",
            backgroundColor: location.pathname.startsWith("/clips")
              ? "rgba(124,58,237,0.12)"
              : "transparent",
            "&:hover": {
              color: "#a78bfa",
              backgroundColor: "rgba(124,58,237,0.08)",
            },
            transition: "all 0.2s ease",
          }}
        >
          <VideoLibraryIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <Tooltip title="Configurações" placement="right">
        <IconButton
          onClick={() => navigate("/settings")}
          sx={{
            color: isActive("/settings") ? "#a78bfa" : "rgba(255,255,255,0.4)",
            backgroundColor: isActive("/settings")
              ? "rgba(124,58,237,0.12)"
              : "transparent",
            "&:hover": {
              color: "#a78bfa",
              backgroundColor: "rgba(124,58,237,0.08)",
            },
            transition: "all 0.2s ease",
          }}
        >
          <SettingsIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <Box sx={{ flex: 1 }} />

      <Tooltip title="Sair" placement="right">
        <IconButton
          onClick={signOut}
          sx={{
            color: "rgba(255,255,255,0.4)",
            "&:hover": { color: "#ef4444" },
            transition: "all 0.2s ease",
          }}
        >
          <LogoutIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <Avatar
        sx={{
          width: 30,
          height: 30,
          fontSize: 13,
          fontWeight: 600,
          backgroundColor: "rgba(124,58,237,0.2)",
          color: "#a78bfa",
          border: "1px solid rgba(124,58,237,0.3)",
        }}
      >
        {initial}
      </Avatar>
    </Box>
  );
}
