import { useState, useEffect, useRef } from "react";
import {
  Box,
  Typography,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  IconButton,
  Button,
  CircularProgress,
  TextField,
} from "@mui/material";
import StarIcon from "@mui/icons-material/Star";
import CloseIcon from "@mui/icons-material/Close";
import PhotoLibraryIcon from "@mui/icons-material/PhotoLibrary";
import { getBatchThumbnails } from "../lib/api";

interface Photo {
  name: string;
  url: string;
  recommended: boolean;
}

interface PhotoGridProps {
  photos: Photo[];
  onSelect: (name: string, instructions?: string) => void;
  disabled?: boolean;
}

export default function PhotoGrid({
  photos,
  onSelect,
  disabled,
}: PhotoGridProps) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [instructions, setInstructions] = useState("");
  const [signedUrls, setSignedUrls] = useState<Record<string, string>>({});
  const [loadingUrls, setLoadingUrls] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Fetch all signed URLs in one batch when dialog opens
  useEffect(() => {
    if (!open || photos.length === 0) return;

    // Abort any previous batch
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoadingUrls(true);
    const filenames = photos.map((p) => p.name);

    getBatchThumbnails("personal-photos", filenames, 200)
      .then((urlMap) => {
        if (controller.signal.aborted) return;
        setSignedUrls(urlMap);
      })
      .catch(() => {
        // ignore
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingUrls(false);
      });

    return () => controller.abort();
  }, [open, photos]);

  // Abort all image loading when dialog closes
  const handleClose = () => {
    abortRef.current?.abort();
    setOpen(false);
  };

  const handleSelect = (name: string) => {
    if (disabled) return;
    setSelected(name);
  };

  const handleConfirm = () => {
    if (selected) {
      onSelect(selected, instructions.trim() || undefined);
      abortRef.current?.abort();
      setOpen(false);
    }
  };

  return (
    <Box sx={{ mt: 1 }}>
      <Typography
        variant="body2"
        sx={{ mb: 1.5, color: "rgba(255,255,255,0.6)" }}
      >
        Selecione uma foto para a thumbnail:
      </Typography>

      <Button
        variant="outlined"
        startIcon={<PhotoLibraryIcon />}
        onClick={() => setOpen(true)}
        disabled={disabled}
        sx={{
          borderColor: "#7c3aed",
          color: "#c4b5fd",
          textTransform: "none",
          fontSize: 14,
          px: 3,
          py: 1.2,
          "&:hover": {
            borderColor: "#a78bfa",
            backgroundColor: "rgba(124,58,237,0.1)",
          },
        }}
      >
        Ver fotos ({photos.length})
      </Button>

      <Dialog
        open={open}
        onClose={handleClose}
        maxWidth="lg"
        fullWidth
        PaperProps={{
          sx: {
            backgroundColor: "#1a1a2e",
            backgroundImage: "none",
            borderRadius: 3,
            maxHeight: "85vh",
          },
        }}
      >
        <DialogTitle
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
            pb: 1.5,
          }}
        >
          <Typography
            variant="h6"
            component="span"
            sx={{ color: "#e2e8f0", fontWeight: 600 }}
          >
            Escolha uma foto
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            {selected && (
              <Button
                variant="contained"
                onClick={handleConfirm}
                sx={{
                  backgroundColor: "#7c3aed",
                  textTransform: "none",
                  fontWeight: 600,
                  px: 3,
                  "&:hover": { backgroundColor: "#6d28d9" },
                }}
              >
                Usar esta foto
              </Button>
            )}
            <IconButton onClick={handleClose} sx={{ color: "#94a3b8" }}>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent sx={{ pt: 3 }}>
          {loadingUrls ? (
            <Box>
              <Typography
                variant="subtitle2"
                sx={{
                  color: "rgba(255,255,255,0.5)",
                  mb: 1.5,
                  fontWeight: 600,
                }}
              >
                Carregando {photos.length} fotos...
              </Typography>
              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
                  gap: 2,
                }}
              >
                {Array.from({ length: Math.min(photos.length, 12) }).map(
                  (_, i) => (
                    <Box
                      key={i}
                      sx={{
                        borderRadius: 2,
                        height: 160,
                        backgroundColor: "rgba(255,255,255,0.03)",
                        animation: "pulse 1.5s ease-in-out infinite",
                        "@keyframes pulse": {
                          "0%, 100%": {
                            opacity: 0.4,
                          },
                          "50%": {
                            opacity: 0.8,
                          },
                        },
                        animationDelay: `${i * 0.1}s`,
                      }}
                    />
                  )
                )}
              </Box>
            </Box>
          ) : (
            <>
              {/* Recommended section */}
              {photos.some((p) => p.recommended) && (
                <Box sx={{ mb: 3 }}>
                  <Typography
                    variant="subtitle2"
                    sx={{ color: "#a78bfa", mb: 1.5, fontWeight: 600 }}
                  >
                    Recomendadas para este tema
                  </Typography>
                  <Box
                    sx={{
                      display: "grid",
                      gridTemplateColumns:
                        "repeat(auto-fill, minmax(200px, 1fr))",
                      gap: 2,
                    }}
                  >
                    {photos
                      .filter((p) => p.recommended)
                      .map((photo) => (
                        <PhotoCard
                          key={photo.name}
                          photo={photo}
                          signedUrl={signedUrls[photo.name]}
                          selected={selected === photo.name}
                          onSelect={handleSelect}
                        />
                      ))}
                  </Box>
                </Box>
              )}

              {/* All photos */}
              <Box>
                {photos.some((p) => p.recommended) && (
                  <Typography
                    variant="subtitle2"
                    sx={{
                      color: "rgba(255,255,255,0.5)",
                      mb: 1.5,
                      fontWeight: 600,
                    }}
                  >
                    Todas as fotos
                  </Typography>
                )}
                <Box
                  sx={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(200px, 1fr))",
                    gap: 2,
                  }}
                >
                  {photos
                    .filter((p) => !p.recommended)
                    .map((photo) => (
                      <PhotoCard
                        key={photo.name}
                        photo={photo}
                        signedUrl={signedUrls[photo.name]}
                        selected={selected === photo.name}
                        onSelect={handleSelect}
                      />
                    ))}
                </Box>
              </Box>
            </>
          )}

          {/* Optional instructions */}
          {selected && (
            <Box
              sx={{
                mt: 3,
                pt: 2,
                borderTop: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              <Typography
                variant="subtitle2"
                sx={{ color: "rgba(255,255,255,0.5)", mb: 1 }}
              >
                Alguma alteração na foto? (opcional)
              </Typography>
              <TextField
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                placeholder='ex: "adicionar um boné", "expressão séria", "mais zoom"'
                size="small"
                fullWidth
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleConfirm();
                  }
                }}
                sx={{
                  "& .MuiOutlinedInput-root": {
                    color: "#e2e8f0",
                    backgroundColor: "rgba(0,0,0,0.2)",
                    borderRadius: 2,
                    "& fieldset": {
                      borderColor: "rgba(124,58,237,0.3)",
                    },
                    "&:hover fieldset": {
                      borderColor: "rgba(124,58,237,0.5)",
                    },
                    "&.Mui-focused fieldset": {
                      borderColor: "#7c3aed",
                    },
                  },
                  "& .MuiInputBase-input::placeholder": {
                    color: "rgba(255,255,255,0.3)",
                  },
                }}
              />
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
}

function PhotoCard({
  photo,
  signedUrl,
  selected,
  onSelect,
}: {
  photo: Photo;
  signedUrl?: string;
  selected: boolean;
  onSelect: (name: string) => void;
}) {
  return (
    <Box
      onClick={() => onSelect(photo.name)}
      sx={{
        position: "relative",
        borderRadius: 2,
        overflow: "hidden",
        cursor: "pointer",
        border: selected ? "3px solid #7c3aed" : "3px solid transparent",
        boxShadow: selected ? "0 0 20px rgba(124,58,237,0.4)" : "none",
        transition: "all 0.2s ease",
        "&:hover": {
          transform: "scale(1.02)",
          borderColor: selected ? "#7c3aed" : "rgba(124,58,237,0.5)",
        },
      }}
    >
      {signedUrl ? (
        <Box
          component="img"
          src={signedUrl}
          alt={photo.name}
          loading="lazy"
          sx={{
            width: "100%",
            height: 160,
            objectFit: "cover",
            display: "block",
          }}
        />
      ) : (
        <Box
          sx={{
            width: "100%",
            height: 160,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "rgba(255,255,255,0.03)",
          }}
        >
          <CircularProgress size={20} sx={{ color: "#7c3aed" }} />
        </Box>
      )}
      {photo.recommended && (
        <Chip
          icon={<StarIcon sx={{ fontSize: 14 }} />}
          label="Match"
          size="small"
          sx={{
            position: "absolute",
            top: 8,
            right: 8,
            backgroundColor: "rgba(124,58,237,0.85)",
            color: "#fff",
            fontSize: 11,
            height: 24,
          }}
        />
      )}
      {selected && (
        <Box
          sx={{
            position: "absolute",
            inset: 0,
            backgroundColor: "rgba(124,58,237,0.15)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Box
            sx={{
              width: 32,
              height: 32,
              borderRadius: "50%",
              backgroundColor: "#7c3aed",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontSize: 18,
              fontWeight: 700,
            }}
          >
            ✓
          </Box>
        </Box>
      )}
      <Box
        sx={{
          px: 1,
          py: 0.5,
          backgroundColor: "rgba(0,0,0,0.6)",
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
        }}
      >
        <Typography
          variant="caption"
          sx={{
            color: "rgba(255,255,255,0.7)",
            fontSize: 11,
            display: "block",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {photo.name}
        </Typography>
      </Box>
    </Box>
  );
}
