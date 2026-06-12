import { ImageResponse } from "next/og";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 180,
          height: 180,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 14,
          background: "white",
          borderRadius: 40,
        }}
      >
        <div style={{ width: 38, height: 120, borderRadius: 99, background: "#006a4e" }} />
        <div style={{ width: 38, height: 120, borderRadius: 99, background: "#ffce00" }} />
        <div style={{ width: 38, height: 120, borderRadius: 99, background: "#d21034" }} />
      </div>
    ),
    { ...size },
  );
}
