import BotiqBotIcon from "./BotiqBotIcon";

export default function BotiqAvatar({
  size = 36,
  color = "#272163",
  background = "linear-gradient(135deg, #272163, #3a3490)",
  online = false,
}) {
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <div
        style={{
          width: size,
          height: size,
          borderRadius: "50%",
          background,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: `0 4px 14px ${color}35`,
        }}
      >
        <BotiqBotIcon size={Math.round(size * 0.68)} color={color} light />
      </div>

      {online && (
        <span
          style={{
            position: "absolute",
            right: 0,
            bottom: 0,
            width: Math.max(9, size * 0.24),
            height: Math.max(9, size * 0.24),
            borderRadius: "50%",
            background: "#4ade80",
            border: "2px solid #fff",
            boxShadow: "0 0 8px #4ade80",
          }}
        />
      )}
    </div>
  );
}
