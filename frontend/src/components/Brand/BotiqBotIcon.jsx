export default function BotiqBotIcon({
  size = 40,
  color = "#272163",
  accent = "#4f46e5",
  light = false,
  strokeWidth = 2,
}) {
  const main = light ? "#ffffff" : color;
  const soft = light ? "rgba(255,255,255,0.25)" : `${color}18`;
  const eye = light ? "#ffffff" : accent;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      aria-hidden="true"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect
        x="14"
        y="18"
        width="36"
        height="30"
        rx="10"
        fill={soft}
        stroke={main}
        strokeWidth={strokeWidth}
      />
      <path
        d="M24 18v-4c0-2.2 1.8-4 4-4h8c2.2 0 4 1.8 4 4v4"
        stroke={main}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      <circle cx="26" cy="33" r="3.4" fill={eye} />
      <circle cx="38" cy="33" r="3.4" fill={eye} />
      <path
        d="M27 41h10"
        stroke={main}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      <path
        d="M14 31H9M55 31h-5"
        stroke={main}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      <path
        d="M21 52h22"
        stroke={main}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      <path
        d="M46 14l5-5"
        stroke={accent}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      <circle cx="53" cy="7" r="3" fill={accent} />
    </svg>
  );
}


