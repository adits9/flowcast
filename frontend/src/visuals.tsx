import type { Category, Location } from "./types";

export function Logo({ small = false }: { small?: boolean }) {
  return (
    <span className={`logo-mark ${small ? "small" : ""}`} aria-hidden="true">
      <span />
      <span />
      <span />
    </span>
  );
}

export function VenueArt({
  category,
  variant = 0,
}: {
  category: Category;
  variant?: number;
}) {
  return (
    <div
      className={`venue-art art-${category} variant-${variant % 3}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 400 110" preserveAspectRatio="xMidYMid slice">
        <circle className="art-sun" cx="325" cy="24" r="16" />
        <path
          className="art-ground"
          d="M0 93 Q100 67 205 91 T400 80 V110 H0Z"
        />
        {category === "dining" ? (
          <g>
            <path className="art-shadow" d="M82 94H309l-18 13H62Z" />
            <rect
              className="art-building"
              x="99"
              y="35"
              width="203"
              height="58"
              rx="3"
            />
            <path className="art-roof" d="M84 36l32-25h164l36 25Z" />
            <path className="art-awning" d="M104 45h193l8 16H96Z" />
            {[109, 139, 169, 199, 229, 259].map((x) => (
              <path key={x} fill="#f6eee1" d={`M${x} 45h15l3 16h-21Z`} />
            ))}
            <rect
              className="art-window"
              x="113"
              y="69"
              width="48"
              height="24"
              rx="2"
            />
            <rect
              className="art-window"
              x="184"
              y="66"
              width="31"
              height="27"
              rx="2"
            />
            <rect
              className="art-window"
              x="239"
              y="69"
              width="48"
              height="24"
              rx="2"
            />
            <path
              className="art-line"
              d="M127 69v24m20-24v24m108-24v24m18-24v24"
            />
            <path
              className="art-tree"
              d="M53 82q-23-27 0-46q23 19 0 46m287 0q-23-27 0-46q23 19 0 46"
            />
            <path className="art-line" d="M53 64v29m287-29v29" />
          </g>
        ) : category === "study" ? (
          <g>
            <path className="art-shadow" d="M76 94h251l-28 14H64Z" />
            <rect
              className="art-building"
              x="97"
              y="32"
              width="212"
              height="62"
            />
            <path className="art-roof" d="M83 33L202 5l121 28Z" />
            <path fill="#f0e9dd" d="M92 38h223v8H92Z" />
            {[111, 155, 199, 243, 287].map((x) => (
              <g key={x}>
                <rect fill="#ede6d8" x={x} y="45" width="12" height="45" />
                <rect fill="#f7f2e9" x={x - 3} y="87" width="18" height="7" />
              </g>
            ))}
            {[131, 175, 219, 263].map((x) => (
              <rect
                key={x}
                className="art-window"
                x={x}
                y="54"
                width="17"
                height="28"
                rx="8"
              />
            ))}
            <path
              className="art-tree"
              d="M53 88q-26-35 0-54q26 19 0 54m300-4q-19-23 0-35q19 12 0 35"
            />
            <path className="art-line" d="M53 68v28m300-30v29" />
          </g>
        ) : (
          <g>
            <path className="art-shadow" d="M76 95h243l-29 13H56Z" />
            <rect
              className="art-building"
              x="88"
              y="37"
              width="220"
              height="57"
              rx="3"
            />
            <path className="art-roof" d="M87 37L113 15h168l28 22Z" />
            <path className="art-window" d="M100 48h83v36h-83Z" />
            <path
              className="art-line"
              d="M121 48v36m21-36v36m21-36v36m-63-18h83"
            />
            <rect
              className="art-window"
              x="209"
              y="48"
              width="85"
              height="36"
              rx="2"
            />
            <path
              className="art-line"
              d="M229 48v36m21-36v36m23-36v36m-64-18h85"
            />
            <path className="art-awning" d="M187 37h17v57h-17Z" />
            <circle className="art-tree" cx="51" cy="65" r="20" />
            <path className="art-line" d="M51 63v31" />
            <path
              className="art-line"
              d="M336 50v42m-13-38h26m-26 32h26"
              strokeWidth="5"
            />
          </g>
        )}
      </svg>
    </div>
  );
}

export function ForecastChart({
  location,
  timezone,
}: {
  location: Location;
  timezone: string;
}) {
  if (!location.forecast.length)
    return (
      <div className="chart-empty">
        Forecasts will appear when fresh observations and a trained model are
        available.
      </div>
    );
  const points = [
    {
      percent: location.percent,
      lower_percent: location.percent,
      upper_percent: location.percent,
      at: new Date().toISOString(),
      minutes_ahead: 0,
    },
    ...location.forecast,
  ];
  const x = (index: number) => 48 + index * 53;
  const y = (percent: number) => 166 - percent * 1.3;
  const curve = points
    .map((point, index) => `${x(index)},${y(point.percent)}`)
    .join(" ");
  const band = [
    ...points.map((point, index) => `${x(index)},${y(point.upper_percent)}`),
    ...points
      .map((point, index) => `${x(index)},${y(point.lower_percent)}`)
      .reverse(),
  ].join(" ");
  return (
    <svg
      className="forecast-chart"
      viewBox="0 0 510 208"
      role="img"
      aria-label={`Predicted occupancy for ${location.name} over the next two hours, with estimated error range`}
    >
      {[0, 25, 50, 75, 100].map((value) => (
        <g key={value}>
          <line
            x1="48"
            x2="472"
            y1={y(value)}
            y2={y(value)}
            stroke="#e9eaf0"
            strokeDasharray="4 5"
          />
          <text
            x="38"
            y={y(value) + 4}
            textAnchor="end"
            className="chart-label"
          >
            {value}%
          </text>
        </g>
      ))}
      <polygon points={band} fill="#ece9ff" />
      <polyline
        points={curve}
        stroke="#6b62ed"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      {points
        .filter((_, index) => index % 2 === 0)
        .map((point, index) => (
          <g key={point.minutes_ahead}>
            <circle
              cx={x(index * 2)}
              cy={y(point.percent)}
              r="4"
              fill="#6b62ed"
              stroke="white"
              strokeWidth="2"
            />
            <text
              x={x(index * 2)}
              y="193"
              textAnchor="middle"
              className="chart-label"
            >
              {index === 0
                ? "Now"
                : new Date(point.at).toLocaleTimeString("en-US", {
                    hour: "numeric",
                    minute: "2-digit",
                    timeZone: timezone,
                  })}
            </text>
          </g>
        ))}
    </svg>
  );
}
