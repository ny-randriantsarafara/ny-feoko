"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

type FormState = "idle" | "sending" | "sent" | "error";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [formState, setFormState] = useState<FormState>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const supabase = createClient();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!email.trim()) return;

    setFormState("sending");
    setErrorMessage("");

    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });

    if (error) {
      setFormState("error");
      setErrorMessage(error.message);
      return;
    }

    setFormState("sent");
  }

  if (formState === "sent") {
    return (
      <div style={containerStyle}>
        <div style={cardStyle}>
          <h1 style={{ margin: 0, fontSize: 24 }}>Check your email</h1>
          <p style={{ color: "#888", lineHeight: 1.5 }}>
            A magic link has been sent to <strong style={{ color: "#e0e0e0" }}>{email}</strong>.
            Click the link to sign in.
          </p>
          <button
            onClick={() => setFormState("idle")}
            style={linkButtonStyle}
          >
            Use a different email
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        <h1 style={{ margin: 0, fontSize: 24 }}>Ambara Transcript Editor</h1>
        <p style={{ color: "#888", margin: "8px 0 24px" }}>
          Sign in with your email to start labelling
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            style={inputStyle}
          />
          <button
            type="submit"
            disabled={formState === "sending"}
            style={submitButtonStyle}
          >
            {formState === "sending" ? "Sending..." : "Send magic link"}
          </button>
        </form>

        {formState === "error" && (
          <p style={{ color: "#ef4444", fontSize: 13, marginTop: 12 }}>
            {errorMessage}
          </p>
        )}
      </div>
    </div>
  );
}

const containerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "100vh",
};

const cardStyle: React.CSSProperties = {
  width: 380,
  padding: 32,
  background: "#111",
  border: "1px solid #333",
  borderRadius: 12,
};

const inputStyle: React.CSSProperties = {
  padding: "10px 14px",
  fontSize: 15,
  background: "#1e1e1e",
  color: "#e0e0e0",
  border: "1px solid #333",
  borderRadius: 6,
  outline: "none",
};

const submitButtonStyle: React.CSSProperties = {
  padding: "10px 16px",
  fontSize: 15,
  fontWeight: 600,
  background: "#166534",
  color: "white",
  border: "none",
  borderRadius: 6,
  cursor: "pointer",
};

const linkButtonStyle: React.CSSProperties = {
  background: "none",
  border: "none",
  color: "#3b82f6",
  cursor: "pointer",
  fontSize: 14,
  padding: 0,
};
