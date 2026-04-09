import { Box, Typography, Chip } from "@mui/material";
import StarIcon from "@mui/icons-material/Star";

interface Photo {
  name: string;
  url: string;
  recommended: boolean;
}

interface PhotoGridProps {
  photos: Photo[];
  onSelect: (name: string) => void;
  disabled?: boolean;
}

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;

export default function PhotoGrid({
  photos,
  onSelect,
  disabled,
}: PhotoGridProps) {
  return (
    <Box sx={{ mt: 1 }}>
      <Typography
        variant="body2"
        sx={{ mb: 1.5, color: "rgba(255,255,255,0.6)" }}
      >
        Select a photo for the thumbnail:
      </Typography>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: 1,
        }}
      >
        {photos.map((photo) => (
          <Box
            key={photo.name}
            onClick={() => !disabled && onSelect(photo.name)}
            sx={{
              position: "relative",
              borderRadius: 2,
              overflow: "hidden",
              cursor: disabled ? "default" : "pointer",
              border: photo.recommended
                ? "2px solid #7c3aed"
                : "2px solid transparent",
              opacity: disabled ? 0.5 : 1,
              transition: "all 0.2s ease",
              "&:hover": disabled
                ? {}
                : {
                    transform: "scale(1.03)",
                    borderColor: "#7c3aed",
                  },
            }}
          >
            <Box
              component="img"
              src={`${SUPABASE_URL}/storage/v1/object/public/personal-photos/${photo.url.split("/personal-photos/")[1]}`}
              alt={photo.name}
              sx={{
                width: "100%",
                height: 120,
                objectFit: "cover",
                display: "block",
              }}
              onError={(e: React.SyntheticEvent<HTMLImageElement>) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
            {photo.recommended && (
              <Chip
                icon={<StarIcon sx={{ fontSize: 14 }} />}
                label="Match"
                size="small"
                sx={{
                  position: "absolute",
                  top: 4,
                  right: 4,
                  backgroundColor: "rgba(124,58,237,0.85)",
                  color: "#fff",
                  fontSize: 10,
                  height: 22,
                }}
              />
            )}
          </Box>
        ))}
      </Box>
    </Box>
  );
}
