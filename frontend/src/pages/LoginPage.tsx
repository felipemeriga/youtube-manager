import { useState, FormEvent, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, TextField } from "@mui/material";
import { supabase } from "../lib/supabase";
import { useAuth } from "../components/AuthProvider";
import { Button } from "../ds/Button";
import { Card } from "../ds/Card";
import { Stack } from "../ds/Stack";
import { palette, typography } from "../ds/tokens";

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

    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setError(error.message);
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "16px",
        background: palette.bg.canvas,
      }}
    >
      <Card padded style={{ width: "100%", maxWidth: 400 }}>
        <Stack gap={6} align="stretch">
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: 12,
                background: palette.accent[50],
                border: `1px solid ${palette.border.default}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: palette.accent[500],
                ...typography.scale.title,
              }}
              aria-label="YouTube Manager"
            >
              YM
            </div>
            <h1
              style={{
                ...typography.scale.display,
                color: palette.text.primary,
                margin: 0,
                textAlign: "center",
              }}
            >
              YouTube Manager
            </h1>
          </div>

          {error && <Alert severity="error">{error}</Alert>}

          <form onSubmit={handleSubmit}>
            <Stack gap={3}>
              <TextField
                fullWidth
                label="E-mail"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <TextField
                fullWidth
                label="Senha"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <Button type="submit" disabled={loading} style={{ width: "100%", padding: "10px 14px" }}>
                {loading ? "Entrando..." : "Entrar"}
              </Button>
            </Stack>
          </form>
        </Stack>
      </Card>
    </div>
  );
}
