import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 32,
          height: 32,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 3,
        }}
      >
        <div style={{ width: 7, height: 22, borderRadius: 99, background: "#006a4e" }} />
        <div style={{ width: 7, height: 22, borderRadius: 99, background: "#ffce00" }} />
        <div style={{ width: 7, height: 22, borderRadius: 99, background: "#d21034" }} />
      </div>
    ),
    { ...size },
  );
}
