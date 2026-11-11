/** Original schematic icon; no team logos or proprietary geometry. Nose points up. */
export default function CarGlyph({
  color,
  label,
}: {
  color: string;
  label?: string;
}) {
  return (
    <g>
      <rect x="-12" y="-17" width="24" height="5" rx="1" fill={color} />
      <rect x="-10" y="13" width="20" height="5" rx="1" fill={color} />
      <path
        d="M-3 -15 L3 -15 L7 10 L4 15 L-4 15 L-7 10 Z"
        fill={color}
        stroke="#fff"
        strokeWidth=".6"
      />
      <ellipse cx="0" cy="2" rx="3" ry="5" fill="#171721" />
      {[-1, 1].flatMap((side) =>
        [-10, 10].map((y) => (
          <rect
            key={`${side}-${y}`}
            x={side * 11 - 3}
            y={y - 4}
            width="6"
            height="9"
            rx="1"
            fill="#101015"
            stroke="#868698"
            strokeWidth=".5"
          />
        )),
      )}
      {label && (
        <text y="32" textAnchor="middle" fontSize="12" fill="#fff">
          {label}
        </text>
      )}
    </g>
  );
}
export function teamColor(team: string) {
  const lower = team.toLowerCase();
  return lower.includes("mclaren")
    ? "#ff8700"
    : lower.includes("ferrari")
      ? "#ef3340"
      : lower.includes("mercedes")
        ? "#27f4d2"
        : lower.includes("red bull")
          ? "#438cff"
          : lower.includes("williams")
            ? "#64c4ff"
            : lower.includes("aston")
              ? "#37b69c"
              : lower.includes("alpine")
                ? "#fa86cb"
                : "#c4c9d6";
}
