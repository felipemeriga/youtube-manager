import {
  Dialog as MuiDialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  type DialogProps,
} from "@mui/material";

export { DialogActions, DialogContent, DialogTitle };
export function Dialog(props: DialogProps) {
  return <MuiDialog {...props} />;
}
