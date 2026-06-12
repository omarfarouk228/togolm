import { ImageResponse } from "next/og";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "#f8fafc",
          fontFamily: "sans-serif",
        }}
      >
        {/* 3-bar logo */}
        <div style={{ display: "flex", gap: 14, marginBottom: 48 }}>
          <div style={{ width: 28, height: 96, borderRadius: 99, background: "#006a4e" }} />
          <div style={{ width: 28, height: 96, borderRadius: 99, background: "#ffce00" }} />
          <div style={{ width: 28, height: 96, borderRadius: 99, background: "#d21034" }} />
        </div>

        <div
          style={{
            fontSize: 88,
            fontWeight: 800,
            color: "#006a4e",
            letterSpacing: "-2px",
            marginBottom: 24,
          }}
        >
          TogoLM
        </div>

        <div
          style={{
            fontSize: 34,
            color: "#64748b",
            maxWidth: 700,
            textAlign: "center",
            lineHeight: 1.4,
          }}
        >
          La première infrastructure IA open-source centrée sur le Togo
        </div>

        {/* Bottom badge */}
        <div
          style={{
            position: "absolute",
            bottom: 48,
            display: "flex",
            alignItems: "center",
            gap: 10,
            background: "#006a4e18",
            border: "1px solid #006a4e30",
            borderRadius: 99,
            padding: "10px 24px",
          }}
        >
          <div style={{ width: 8, height: 8, borderRadius: 99, background: "#006a4e" }} />
          <span style={{ fontSize: 22, color: "#006a4e", fontWeight: 600 }}>
            Corpus · Recherche · Assistant IA · API
          </span>
        </div>
      </div>
    ),
    { ...size },
  );
}
