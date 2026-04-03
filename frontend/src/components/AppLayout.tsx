import { Box } from "@mui/material";
import { Outlet } from "react-router-dom";
import IconRail from "./IconRail";

export default function AppLayout() {
  return (
    <Box sx={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <IconRail />
      <Box sx={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <Outlet />
      </Box>
    </Box>
  );
}
