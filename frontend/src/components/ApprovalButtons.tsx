import { Box, Button } from "@mui/material";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import SaveIcon from "@mui/icons-material/Save";
import RefreshIcon from "@mui/icons-material/Refresh";

interface ApprovalButtonsProps {
  type: "plan" | "image";
  onApprove: () => void;
  onReject: () => void;
  disabled?: boolean;
}

export default function ApprovalButtons({ type, onApprove, onReject, disabled }: ApprovalButtonsProps) {
  if (type === "plan") {
    return (
      <Box sx={{ display: "flex", gap: 1, mt: 1.5 }}>
        <Button
          variant="contained"
          startIcon={<CheckIcon />}
          onClick={onApprove}
          disabled={disabled}
          sx={{ background: "linear-gradient(135deg, #059669, #10b981)" }}
        >
          Approve
        </Button>
        <Button
          variant="outlined"
          startIcon={<CloseIcon />}
          onClick={onReject}
          disabled={disabled}
          sx={{ borderColor: "rgba(239,68,68,0.5)", color: "#ef4444" }}
        >
          Reject
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: "flex", gap: 1, mt: 1.5 }}>
      <Button
        variant="contained"
        startIcon={<SaveIcon />}
        onClick={onApprove}
        disabled={disabled}
        sx={{ background: "linear-gradient(135deg, #059669, #10b981)" }}
      >
        Save to Outputs
      </Button>
      <Button
        variant="outlined"
        startIcon={<RefreshIcon />}
        onClick={onReject}
        disabled={disabled}
        sx={{ borderColor: "rgba(124,58,237,0.5)", color: "#7c3aed" }}
      >
        Regenerate
      </Button>
    </Box>
  );
}
