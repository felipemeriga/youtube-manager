import { Dialog, IconButton, Box } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useEffect, useState } from "react";
import type { ClipCandidate } from "../../types/clips";
import { clipsApi } from "../../api/clips";

export default function ClipPreviewModal({
  candidate, open, onClose,
}: { candidate: ClipCandidate | null; open: boolean; onClose: () => void }) {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!candidate) return;
    clipsApi.previewUrl(candidate.id).then(r => setUrl(r.url));
  }, [candidate]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <Box sx={{ position: "relative", bgcolor: "black" }}>
        <IconButton
          onClick={onClose}
          sx={{ position: "absolute", top: 8, right: 8, color: "white", zIndex: 1 }}
        >
          <CloseIcon />
        </IconButton>
        {url && <video src={url} controls autoPlay style={{ width: "100%" }} />}
      </Box>
    </Dialog>
  );
}
