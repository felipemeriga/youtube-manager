import { Box, IconButton, Tooltip } from "@mui/material";
import ChatIcon from "@mui/icons-material/Chat";
import PhotoLibraryIcon from "@mui/icons-material/PhotoLibrary";
import LogoutIcon from "@mui/icons-material/Logout";
import SettingsIcon from "@mui/icons-material/Settings";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthProvider";

export default function IconRail() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signOut } = useAuth();

  const isActive = (path: string) => location.pathname === path;

  return (
    <Box
      sx={{
        width: 56,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        py: 2,
        gap: 1,
        borderRight: "1px solid rgba(255,255,255,0.08)",
        backgroundColor: "rgba(0,0,0,0.3)",
      }}
    >
      <Box
        component="img"
        src="/logo.svg"
        alt="YouTube Manager"
        sx={{ width: 32, height: 32, mb: 2, borderRadius: 1 }}
      />

      <Tooltip title="Chat" placement="right">
        <IconButton
          onClick={() => navigate("/")}
          sx={{
            color: isActive("/") ? "#7c3aed" : "rgba(255,255,255,0.5)",
            "&:hover": { color: "#7c3aed" },
          }}
        >
          <ChatIcon />
        </IconButton>
      </Tooltip>

      <Tooltip title="Assets" placement="right">
        <IconButton
          onClick={() => navigate("/assets")}
          sx={{
            color: isActive("/assets") ? "#7c3aed" : "rgba(255,255,255,0.5)",
            "&:hover": { color: "#7c3aed" },
          }}
        >
          <PhotoLibraryIcon />
        </IconButton>
      </Tooltip>

      <Tooltip title="Settings" placement="right">
        <IconButton
          onClick={() => navigate("/settings")}
          sx={{
            color: isActive("/settings") ? "#7c3aed" : "rgba(255,255,255,0.5)",
            "&:hover": { color: "#7c3aed" },
          }}
        >
          <SettingsIcon />
        </IconButton>
      </Tooltip>

      <Box sx={{ flex: 1 }} />

      <Tooltip title="Sign out" placement="right">
        <IconButton
          onClick={signOut}
          sx={{
            color: "rgba(255,255,255,0.5)",
            "&:hover": { color: "#ef4444" },
          }}
        >
          <LogoutIcon />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
