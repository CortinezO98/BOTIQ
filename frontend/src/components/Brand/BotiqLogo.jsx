import BotiqBotIcon from "./BotiqBotIcon";

export default function BotiqLogo({
  variant = "default",
  size = "md",
  showSubtitle = false,
  color = "#272163",
}) {
  const isLight = variant === "light";

  const sizes = {
    sm: { icon: 28, title: 16, subtitle: 10 },
    md: { icon: 38, title: 22, subtitle: 12 },
    lg: { icon: 56, title: 34, subtitle: 14 },
  };

  const s = sizes[size] || sizes.md;
  const textColor = isLight ? "#ffffff" : color;
  const subtitleColor = isLight ? "rgba(255,255,255,0.72)" : "#6b6b8a";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: size === "lg" ? 14 : 10 }}>
      <BotiqBotIcon size={s.icon} color={color} light={isLight} />
      <div style={{ lineHeight: 1 }}>
        <div
          style={{
            color: textColor,
            fontSize: s.title,
            fontWeight: 850,
            letterSpacing: "-0.7px",
          }}
        >
          BOTIQ
        </div>

        {showSubtitle && (
          <div
            style={{
              marginTop: 5,
              color: subtitleColor,
              fontSize: s.subtitle,
              fontWeight: 500,
              letterSpacing: "0.1px",
              whiteSpace: "nowrap",
            }}
          >
            Asistente Corporativo Inteligente
          </div>
        )}
      </div>
    </div>
  );
}


