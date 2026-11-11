import { useState } from "react";
export default function EngineeringCar({ focus }: { focus: string }) {
  const [moving, setMoving] = useState(true);
  return (
    <div className={`engineering-car ${moving ? "" : "paused"}`}>
      <svg
        viewBox="0 0 700 480"
        role="img"
        aria-label={`Conceptual top-down car schematic highlighting ${focus}`}
      >
        <defs>
          <marker
            id="air-arrow"
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto"
          >
            <path d="M0 0 L10 5 L0 10" fill="#6be2ff" />
          </marker>
        </defs>
        <path
          d="M280 105 L420 105 L440 355 L400 405 L300 405 L260 355 Z"
          fill={focus === "floor" ? "#25608b" : "#303044"}
          stroke="#72728a"
          strokeWidth="3"
        />
        <path
          d="M340 50 L360 50 L380 280 L370 385 L330 385 L320 280 Z"
          fill="#ed3535"
        />
        <ellipse cx="350" cy="230" rx="20" ry="35" fill="#11111c" />
        {[240, 420].flatMap((x) =>
          [130, 330].map((y) => (
            <rect
              key={`${x}-${y}`}
              x={x}
              y={y}
              width="40"
              height="65"
              rx="8"
              fill="#101018"
              stroke="#777"
            />
          )),
        )}
        <rect x="240" y="65" width="220" height="16" rx="3" fill="#b0b0c3" />
        <rect x="265" y="405" width="170" height="18" rx="3" fill="#b0b0c3" />
        {focus === "brakes" &&
          [275, 425].flatMap((x) =>
            [160, 360].map((y) => (
              <circle key={`${x}-${y}`} cx={x} cy={y} r="13" fill="#ff8700" />
            )),
          )}
        {focus === "suspension" &&
          [150, 345].map((y) => (
            <path
              key={y}
              d={`M275 ${y} L330 ${y + 25} L275 ${y + 40} M425 ${y} L370 ${y + 25} L425 ${y + 40}`}
              stroke="#27f4d2"
              strokeWidth="6"
              fill="none"
            />
          ))}
        {focus === "engine" && (
          <rect x="320" y="285" width="60" height="75" rx="8" fill="#f3be41" />
        )}
        {[215, 295, 405, 485].map((x, i) => (
          <path
            className="airflow"
            key={x}
            d={`M${x} 10 Q${x + (i < 2 ? -30 : 30)} 190 ${x} 455`}
            fill="none"
            stroke="#6be2ff"
            strokeWidth="3"
            strokeDasharray="12 14"
            markerEnd="url(#air-arrow)"
          />
        ))}
        <text x="350" y="465" fill="#aaaabe" textAnchor="middle" fontSize="14">
          CONCEPT SCHEMATIC · NOT CFD OR MEASURED AIRFLOW
        </text>
      </svg>
      <button
        className="btn btn--secondary"
        onClick={() => setMoving((v) => !v)}
      >
        {moving ? "Pause concept animation" : "Animate concept"}
      </button>
    </div>
  );
}
