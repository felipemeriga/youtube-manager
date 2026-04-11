import { useState, FormEvent, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  TextField,
  Button,
  Typography,
  Alert,
  Paper,
} from "@mui/material";
import { supabase } from "../lib/supabase";
import { useAuth } from "../components/AuthProvider";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { session } = useAuth();

  useEffect(() => {
    if (session) navigate("/", { replace: true });
  }, [session, navigate]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (error) {
      setError(error.message);
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        background:
          "radial-gradient(ellipse at 20% 50%, rgba(124,58,237,0.08) 0%, transparent 50%), radial-gradient(ellipse at 80% 50%, rgba(59,130,246,0.06) 0%, transparent 50%), linear-gradient(180deg, #0f0f14 0%, #13141f 100%)",
      }}
    >
      <Paper
        sx={{
          p: 4,
          width: 400,
          backdropFilter: "blur(20px)",
          backgroundColor: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: 3,
        }}
      >
        <Box sx={{ display: "flex", justifyContent: "center", mb: 2 }}>
          <Box
            component="img"
            src="/logo.svg"
            alt="YouTube Manager"
            sx={{ width: 64, height: 64, borderRadius: 2 }}
          />
        </Box>
        <Typography
          variant="h4"
          sx={{
            mb: 3,
            textAlign: "center",
            background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          YouTube Manager
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="E-mail"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="Senha"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            sx={{ mb: 3 }}
          />
          <Button
            fullWidth
            type="submit"
            variant="contained"
            disabled={loading}
            sx={{
              background: "linear-gradient(135deg, #7c3aed, #3b82f6)",
              py: 1.5,
            }}
          >
            {loading ? "Entrando..." : "Entrar"}
          </Button>
        </form>
      </Paper>
    </Box>
  );
}
