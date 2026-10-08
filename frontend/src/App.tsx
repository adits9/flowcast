import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Bell,
  BellOff,
  Bookmark,
  CalendarDays,
  Check,
  ChevronDown,
  Clock3,
  CloudSun,
  Coffee,
  Compass,
  Dumbbell,
  GraduationCap,
  HelpCircle,
  LayoutGrid,
  Leaf,
  Map,
  MapPin,
  Search,
  Sparkles,
  TrendingUp,
  Users,
  Waves,
  WifiOff,
  X,
} from "lucide-react";
import { readSaved, request } from "./api";
import { ForecastChart, Logo, VenueArt } from "./visuals";
import type {
  Alert,
  Category,
  Checkin,
  CrowdStatus,
  Location,
  Overview,
} from "./types";

const categories: {
  id: "all" | Category;
  name: string;
  icon: typeof Coffee;
}[] = [
  { id: "all", name: "All spaces", icon: LayoutGrid },
  { id: "dining", name: "Dining", icon: Coffee },
  { id: "fitness", name: "Fitness", icon: Dumbbell },
  { id: "study", name: "Study", icon: GraduationCap },
];
const labels: Record<CrowdStatus, string> = {
  quiet: "Quiet",
  moderate: "A little lively",
  busy: "Busy",
  closed: "Closed",
  unknown: "Awaiting data",
};
type Page = "overview" | "map" | "saved" | "forecasts";

function time(value: string, timezone: string) {
  return new Date(value).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: timezone,
  });
}
function hours(value: number) {
  return value === 0 || value === 24
    ? "12 am"
    : `${value % 12 || 12} ${value < 12 ? "am" : "pm"}`;
}
function Badge({ status }: { status: CrowdStatus }) {
  return (
    <span className={`badge ${status}`}>
      <span className="status-dot" />
      {labels[status]}
    </span>
  );
}

function Modal({
  children,
  onClose,
  label,
  wide = false,
}: {
  children: ReactNode;
  onClose: () => void;
  label: string;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    function key(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const focusable = ref.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a, input, select, [tabindex="0"]',
        );
        if (!focusable?.length) {
          event.preventDefault();
          return;
        }
        const first = focusable[0],
          last = focusable[focusable.length - 1];
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === ref.current)
        ) {
          event.preventDefault();
          last.focus();
        } else if (
          !event.shiftKey &&
          (document.activeElement === last ||
            document.activeElement === ref.current)
        ) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", key);
    return () => {
      document.body.style.overflow = oldOverflow;
      document.removeEventListener("keydown", key);
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div
      className="modal-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        className={`modal ${wide ? "wide" : ""}`}
      >
        <button
          className="icon-button modal-close"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={20} />
        </button>
        {children}
      </div>
    </div>
  );
}

function LocationCard({
  location,
  saved,
  checkedIn,
  onSave,
  onOpen,
  index,
}: {
  location: Location;
  saved: boolean;
  checkedIn: boolean;
  onSave: () => void;
  onOpen: () => void;
  index: number;
}) {
  const next = location.forecast.find((point) => point.minutes_ahead === 30);
  return (
    <article
      className="location-card"
      style={{ animationDelay: `${index * 35}ms` }}
    >
      <div className="card-art-wrap">
        <button
          className="art-link"
          onClick={onOpen}
          aria-label={`View ${location.name}`}
        >
          <VenueArt category={location.category} variant={index} />
        </button>
        <Badge status={location.status} />
        <button
          className={`save-button ${saved ? "saved" : ""}`}
          onClick={onSave}
          aria-label={`${saved ? "Unsave" : "Save"} ${location.name}`}
          aria-pressed={saved}
        >
          <Bookmark size={17} fill={saved ? "currentColor" : "none"} />
        </button>
      </div>
      <div className="card-body">
        <div className="card-category">
          {location.category}
          <span>
            <MapPin size={11} /> {location.walk_minutes} min walk
          </span>
        </div>
        <button className="card-title" onClick={onOpen}>
          {location.name}
          {checkedIn && (
            <span className="checked-in-label">
              <Check size={12} /> Here
            </span>
          )}
        </button>
        <p className="building">{location.building}</p>
        <div className="occupancy-label">
          <span>
            {location.stale
              ? "Occupancy unavailable"
              : location.is_open
                ? `${location.percent}% occupied`
                : "Come back during open hours"}
          </span>
          <span>
            {!location.stale && location.is_open
              ? `${location.occupancy} / ${location.capacity}`
              : `${hours(location.opens)}–${hours(location.closes)}`}
          </span>
        </div>
        <div className={`occupancy-bar ${location.status}`}>
          <span
            style={{
              width: `${location.is_open && !location.stale ? location.percent : 0}%`,
            }}
          />
        </div>
        <div className="card-footer">
          <span>
            <Clock3 size={14} />
            <strong>
              {location.wait_minutes == null || !location.is_open
                ? "—"
                : location.wait_minutes === 0
                  ? "No wait"
                  : `${location.wait_minutes} min`}
            </strong>
            {location.wait_minutes !== null &&
              location.wait_minutes > 0 &&
              " wait"}
          </span>
          <button onClick={onOpen}>
            View forecast <ArrowUpRight size={14} />
          </button>
        </div>
        {next && location.is_open && (
          <div className="card-trend">
            {next.percent < location.percent - 4 ? (
              <ArrowDown size={12} />
            ) : (
              <Activity size={12} />
            )}{" "}
            {next.percent < location.percent - 4
              ? "Getting quieter"
              : next.percent > location.percent + 4
                ? "Picking up soon"
                : "Steady for now"}
            <span>Next 30 min</span>
          </div>
        )}
      </div>
    </article>
  );
}

function CampusMap({
  locations,
  onOpen,
  highlighted,
}: {
  locations: Location[];
  onOpen: (id: string) => void;
  highlighted: string | null;
}) {
  return (
    <div className="campus-map">
      <svg
        className="map-background"
        viewBox="0 0 1000 600"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <rect width="1000" height="600" fill="#edf1e8" />
        <path
          d="M0 307L1000 311M518 0L508 600M0 130L1000 145M0 507L1000 502"
          stroke="#fff"
          strokeWidth="32"
        />
        <path
          d="M0 307L1000 311M518 0L508 600M0 130L1000 145M0 507L1000 502"
          stroke="#dedfd7"
          strokeWidth="2"
          strokeDasharray="7 7"
        />
        <path d="M338 211h316v247H338Z" fill="#d7e5c9" rx="15" />
        <path
          d="M355 227L632 440M632 227L355 440"
          stroke="#f7f6ee"
          strokeWidth="12"
        />
        <ellipse cx="890" cy="207" rx="100" ry="63" fill="#cce4e8" />
        {[
          [118, 75],
          [276, 67],
          [678, 86],
          [857, 79],
          [89, 370],
          [295, 359],
          [692, 380],
          [140, 526],
          [758, 528],
        ].map(([x, y], index) => (
          <rect
            key={index}
            x={x}
            y={y}
            width="80"
            height="50"
            rx="7"
            fill="#dce0d4"
            stroke="#cdd3c6"
            strokeWidth="2"
          />
        ))}
        {[
          [374, 182],
          [618, 189],
          [342, 490],
          [660, 492],
          [909, 369],
          [67, 177],
          [107, 437],
          [909, 545],
          [69, 558],
        ].map(([x, y], index) => (
          <g key={index}>
            <circle cx={x} cy={y} r="16" fill="#b7d0a3" />
            <circle cx={x + 4} cy={y - 4} r="9" fill="#c5dcb4" />
          </g>
        ))}
      </svg>
      <span className="map-place quad">THE QUAD</span>
      <span className="map-place pond">WILLOW POND</span>
      <span className="map-road">UNIVERSITY AVENUE</span>
      {locations.map((location) => (
        <button
          key={location.id}
          className={`map-marker ${location.status} ${highlighted === location.id ? "highlighted" : ""}`}
          style={{ left: `${location.x}%`, top: `${location.y}%` }}
          onClick={() => onOpen(location.id)}
          aria-label={`${location.name}, ${labels[location.status]}`}
        >
          <span className="map-pin">
            {location.category === "study" ? (
              <GraduationCap size={19} />
            ) : location.category === "dining" ? (
              <Coffee size={19} />
            ) : (
              <Dumbbell size={19} />
            )}
          </span>
          <span className="map-label">
            {location.name}
            <small>
              {location.stale
                ? "Awaiting data"
                : location.is_open
                  ? `${location.percent}% occupied`
                  : "Closed"}
            </small>
          </span>
        </button>
      ))}
      <div className="map-legend">
        <span>
          <i className="dot quiet" />
          Quiet
        </span>
        <span>
          <i className="dot moderate" />
          Lively
        </span>
        <span>
          <i className="dot busy" />
          Busy
        </span>
      </div>
      <div className="map-note">
        <Compass size={14} /> Illustrated campus · not to scale
      </div>
    </div>
  );
}

export default function App() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState<
    "connecting" | "live" | "offline"
  >("connecting");
  const [page, setPage] = useState<Page>("overview");
  const [category, setCategory] = useState<"all" | Category>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("recommended");
  const [onlyQuiet, setOnlyQuiet] = useState(false);
  const [saved, setSaved] = useState<string[]>(() =>
    readSaved("flowcast.saved", []),
  );
  const [subscriptions, setSubscriptions] = useState<string[]>(() =>
    readSaved("flowcast.subscriptions", []),
  );
  const subscriptionRef = useRef(subscriptions);
  subscriptionRef.current = subscriptions;
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [showAlerts, setShowAlerts] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const [checkin, setCheckin] = useState<Checkin>({
    location_id: null,
    expires_at: null,
  });
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const [horizon, setHorizon] = useState(30);

  useEffect(() => {
    localStorage.setItem("flowcast.saved", JSON.stringify(saved));
  }, [saved]);
  useEffect(() => {
    localStorage.setItem(
      "flowcast.subscriptions",
      JSON.stringify(subscriptions),
    );
  }, [subscriptions]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket;
    let retry: ReturnType<typeof setTimeout>;
    let attempts = 0;
    function load() {
      request<Overview>("/api/overview")
        .then((value) => {
          if (!disposed) {
            setData(value);
            setError("");
          }
        })
        .catch(() => {
          if (!disposed)
            setError(
              "We couldn’t reach campus updates. Check your connection and try again.",
            );
        });
    }
    function loadCheckin() {
      request<Checkin>("/api/checkins/me")
        .then((value) => {
          if (!disposed) setCheckin(value);
        })
        .catch(() => {});
    }
    function connect() {
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`,
      );
      socket.onopen = () => {
        if (!disposed) {
          setConnection("live");
          attempts = 0;
        }
      };
      socket.onmessage = (event) => {
        if (disposed) return;
        try {
          const payload = JSON.parse(event.data) as {
            type: string;
            data: Overview;
            alerts: Alert[];
          };
          if (payload.type !== "snapshot") return;
          setData(payload.data);
          setError("");
          const relevant = payload.alerts.filter((alert) =>
            subscriptionRef.current.includes(alert.location_id),
          );
          if (relevant.length) {
            setAlerts((previous) => [...relevant, ...previous].slice(0, 30));
            setToast(relevant[0].message);
          }
        } catch {
          /* Ignore malformed events; the polling fallback remains available. */
        }
      };
      socket.onclose = () => {
        if (!disposed) {
          setConnection("offline");
          retry = setTimeout(connect, Math.min(15000, 1000 * 2 ** attempts++));
        }
      };
      socket.onerror = () => socket.close();
    }
    load();
    loadCheckin();
    connect();
    const polling = setInterval(() => {
      if (socket.readyState !== WebSocket.OPEN) load();
      else socket.send("ping");
      loadCheckin();
    }, 20000);
    return () => {
      disposed = true;
      clearTimeout(retry);
      clearInterval(polling);
      socket?.close();
    };
  }, []);

  function toggleSave(id: string) {
    setSaved((previous) =>
      previous.includes(id)
        ? previous.filter((value) => value !== id)
        : [...previous, id],
    );
  }
  function toggleSubscribe(id: string) {
    const adding = !subscriptions.includes(id);
    setSubscriptions((previous) =>
      adding ? [...previous, id] : previous.filter((value) => value !== id),
    );
    setToast(
      adding
        ? "Crowd alerts are on. Keep FlowCast open to receive updates."
        : "Crowd alerts turned off.",
    );
  }
  async function updateCheckin(locationId?: string) {
    setBusy(true);
    try {
      const value = await request<Checkin>(
        locationId ? "/api/checkins" : "/api/checkins/me",
        {
          method: locationId ? "POST" : "DELETE",
          ...(locationId
            ? { body: JSON.stringify({ location_id: locationId }) }
            : {}),
        },
      );
      setCheckin(value);
      setToast(
        locationId
          ? "You’re checked in. Enjoy your space!"
          : "You’re checked out. See you next time.",
      );
      setData(await request<Overview>("/api/overview"));
    } catch (issue) {
      setToast(issue instanceof Error ? issue.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }
  function navigate(next: Page) {
    setPage(next);
    setQuery("");
    setOnlyQuiet(false);
    setShowAlerts(false);
  }

  const locations = data?.locations ?? [];
  const quiet = locations.filter((item) => item.status === "quiet");
  const open = locations.filter((item) => item.is_open);
  const known = open.filter((item) => !item.stale);
  const averageWait = known.length
    ? Math.round(
        known.reduce((total, item) => total + (item.wait_minutes ?? 0), 0) /
          known.length,
      )
    : null;
  const recommendation = [...known].sort(
    (a, b) =>
      Number(a.status !== "quiet") - Number(b.status !== "quiet") ||
      Number(a.category !== "study") - Number(b.category !== "study") ||
      a.percent - b.percent,
  )[0];
  const detail = locations.find((item) => item.id === selected);
  const filtered = locations
    .filter(
      (item) =>
        (category === "all" || category === item.category) &&
        (page !== "saved" || saved.includes(item.id)) &&
        (!onlyQuiet || item.status === "quiet") &&
        `${item.name} ${item.building} ${item.tags.join(" ")}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "walk"
        ? a.walk_minutes - b.walk_minutes
        : sort === "name"
          ? a.name.localeCompare(b.name)
          : Number(!a.is_open || a.stale) - Number(!b.is_open || b.stale) ||
            a.percent - b.percent,
    );
  const date = data
    ? new Date(data.updated_at).toLocaleDateString("en-US", {
        weekday: "long",
        month: "short",
        day: "numeric",
        timeZone: data.timezone,
      })
    : "Your campus, in real time";
  const pageTitles = {
    overview: "Campus overview",
    map: "Campus map",
    saved: "Saved spaces",
    forecasts: "Crowd forecasts",
  };
  const nextEvent = data?.events[0];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="brand"
          onClick={() => navigate("overview")}
          aria-label="FlowCast home"
        >
          <Logo />
          <span>
            FlowCast<span className="brand-dot">.</span>
          </span>
        </button>
        <div className="campus-label">
          <GraduationCap size={17} />
          <div>
            {data?.campus ?? "Your campus"}
            <span>Campus companion</span>
          </div>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          {(
            [
              { id: "overview", icon: LayoutGrid, label: "Overview" },
              { id: "map", icon: Map, label: "Campus map" },
              { id: "saved", icon: Bookmark, label: "Saved spaces" },
              { id: "forecasts", icon: TrendingUp, label: "Forecasts" },
            ] as const
          ).map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "active" : ""}`}
              onClick={() => navigate(item.id)}
              aria-label={item.label}
              aria-current={page === item.id ? "page" : undefined}
            >
              <item.icon size={18} />
              <span className="nav-full">{item.label}</span>
              <span className="nav-short">
                {item.id === "map"
                  ? "Map"
                  : item.id === "saved"
                    ? "Saved"
                    : item.label}
              </span>
              {item.id === "saved" && saved.length > 0 && (
                <span className="nav-count">{saved.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-tip">
          <div className="tip-icon">
            <Sparkles size={20} />
          </div>
          <strong>Good timing changes everything.</strong>
          <p>Find a little room in your day. We’ll help you skip the crowds.</p>
          <button onClick={() => navigate("forecasts")}>
            Plan ahead <ArrowRight size={14} />
          </button>
        </div>
        <div className="sidebar-bottom">
          <button className="help-link" onClick={() => setShowHelp(true)}>
            <HelpCircle size={17} /> About FlowCast <ArrowUpRight size={14} />
          </button>
          <div className="profile-avatar">
            N
            <div>
              <strong>
                {data?.demo_mode ? "Explore the demo" : "Campus explorer"}
              </strong>
              <span>
                {data?.demo_mode ? "No account needed" : "Anonymous check-ins"}
              </span>
            </div>
            <Leaf size={17} />
          </div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="breadcrumb-slash">/</span>
            <strong>{pageTitles[page]}</strong>
          </div>
          <div className="topbar-actions">
            <span className={`live-pill ${connection}`}>
              <span className="status-dot" />
              {connection === "live"
                ? data?.demo_mode
                  ? "Live demo"
                  : "Live updates"
                : connection === "connecting"
                  ? "Connecting"
                  : "Reconnecting"}
            </span>
            <div className="notification-wrap">
              <button
                className={`icon-button notification-button ${showAlerts ? "selected" : ""}`}
                onClick={() => setShowAlerts(!showAlerts)}
                aria-label={`Notifications, ${alerts.length} updates`}
                aria-expanded={showAlerts}
              >
                <Bell size={19} />
                {alerts.length > 0 && <i />}
              </button>
              {showAlerts && (
                <div className="notifications">
                  <div className="notifications-title">
                    <strong>Your crowd alerts</strong>
                    <button onClick={() => setAlerts([])}>Clear</button>
                  </div>
                  {alerts.length ? (
                    alerts.map((alert, index) => (
                      <button
                        className="notification"
                        key={`${alert.at}-${alert.location_id}-${index}`}
                        onClick={() => {
                          setSelected(alert.location_id);
                          setShowAlerts(false);
                        }}
                      >
                        <span className={`notification-icon ${alert.kind}`}>
                          {alert.kind === "quiet" ? (
                            <Leaf size={16} />
                          ) : (
                            <Users size={16} />
                          )}
                        </span>
                        <span>
                          <strong>{alert.message}</strong>
                          <small>{data && time(alert.at, data.timezone)}</small>
                        </span>
                      </button>
                    ))
                  ) : (
                    <div className="notification-empty">
                      <Bell size={25} />
                      <p>A heads-up, right when you need it.</p>
                      <span>
                        Open a space and turn on crowd alerts. Updates appear
                        here while FlowCast is open.
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
            <span className="top-avatar" aria-label="Anonymous campus explorer">
              N
            </span>
          </div>
        </header>

        <main id="main-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">{date}</div>
              <h1>
                {page === "overview" ? "Find your space." : pageTitles[page]}
              </h1>
              <p>
                {page === "overview"
                  ? "Less waiting. More of what you came here for."
                  : page === "map"
                    ? "A little perspective on the places around you."
                    : page === "saved"
                      ? "Your usual spots, with a fresh look at the crowds."
                      : "A better time to arrive is just ahead."}
              </p>
            </div>
            {data && (
              <div className="weather-pill">
                <CloudSun size={24} />
                <div>
                  <strong>{Math.round(data.weather.temperature_c)}°C</strong>
                  <span>
                    {data.weather.source === "demo"
                      ? "Demo weather"
                      : data.weather.source === "unavailable"
                        ? "Weather unavailable"
                        : data.weather.stale
                          ? "Weather needs an update"
                          : data.weather.description}
                  </span>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="error-banner" role="alert">
              <WifiOff size={17} />
              {error}
              <button
                onClick={() =>
                  request<Overview>("/api/overview")
                    .then((value) => {
                      setData(value);
                      setError("");
                    })
                    .catch(() => {})
                }
              >
                Try again
              </button>
            </div>
          )}
          {!data && !error && (
            <div className="loading-state">
              <div className="spinner" />
              <p>Getting a feel for campus…</p>
            </div>
          )}
          {data && (
            <>
              {checkin.location_id && (
                <div className="checkin-banner">
                  <span>
                    <Check size={16} /> You’re at{" "}
                    <strong>
                      {
                        locations.find(
                          (item) => item.id === checkin.location_id,
                        )?.name
                      }
                    </strong>
                    <small>
                      Until{" "}
                      {checkin.expires_at &&
                        time(checkin.expires_at, data.timezone)}
                    </small>
                  </span>
                  <button disabled={busy} onClick={() => updateCheckin()}>
                    Check out <ArrowRight size={14} />
                  </button>
                </div>
              )}
              {page === "overview" && (
                <>
                  <div className="hero-row">
                    <section className="hero">
                      <div className="hero-content">
                        <span className="hero-eyebrow">
                          <span /> A LITTLE ROOM TO BREATHE
                        </span>
                        <h2>
                          Your day flows better
                          <br />
                          without the crowds.
                        </h2>
                        <p>
                          That quiet table. An open treadmill. Your favorite
                          <br className="desktop-break" /> coffee without the
                          line. Find your moment.
                        </p>
                        <button
                          className="primary-button"
                          onClick={() => {
                            setOnlyQuiet(true);
                            setCategory("all");
                            document.getElementById("spaces")?.scrollIntoView({
                              behavior: "smooth",
                              block: "start",
                            });
                          }}
                        >
                          Find a quiet space <ArrowRight size={16} />
                        </button>
                      </div>
                      <div className="hero-graphic" aria-hidden="true">
                        <div className="orbit orbit-one" />
                        <div className="orbit orbit-two" />
                        <div className="orbit orbit-three" />
                        <div className="floating-icon floating-coffee">
                          <Coffee size={28} />
                        </div>
                        <div className="floating-icon floating-book">
                          <GraduationCap size={30} />
                        </div>
                        <div className="floating-icon floating-fitness">
                          <Dumbbell size={26} />
                        </div>
                        <div className="hero-center">
                          <Waves size={42} />
                        </div>
                        <span className="spark spark-one">✦</span>
                        <span className="spark spark-two">✦</span>
                        <span className="hero-tag">
                          <span className="status-dot" /> A good time to go
                        </span>
                      </div>
                    </section>
                    <section className="recommendation">
                      <div className="section-kicker">
                        <Sparkles size={14} /> A LITTLE ROOM FOR YOU
                      </div>
                      {recommendation ? (
                        <>
                          <div className="recommendation-icon">
                            {recommendation.category === "study" ? (
                              <GraduationCap size={26} />
                            ) : recommendation.category === "dining" ? (
                              <Coffee size={26} />
                            ) : (
                              <Dumbbell size={26} />
                            )}
                          </div>
                          <h3>{recommendation.name}</h3>
                          <p>
                            {recommendation.available} open spots. A little
                            space{" "}
                            {recommendation.category === "study"
                              ? "to focus."
                              : recommendation.category === "dining"
                                ? "to recharge."
                                : "to move."}
                          </p>
                          <div className="recommendation-meta">
                            <Badge status={recommendation.status} />
                            <span>
                              <MapPin size={12} />
                              {recommendation.walk_minutes} min away
                            </span>
                          </div>
                          <button
                            onClick={() => setSelected(recommendation.id)}
                          >
                            Take a closer look <ArrowUpRight size={16} />
                          </button>
                        </>
                      ) : (
                        <>
                          <h3>Your space is coming.</h3>
                          <p>
                            Fresh observations will help us find a good spot.
                          </p>
                        </>
                      )}
                    </section>
                  </div>
                  <div className="stats-row">
                    <div className="stat">
                      <span className="stat-icon lavender">
                        <MapPin size={21} />
                      </span>
                      <div>
                        <span>Spaces open now</span>
                        <strong>
                          {open.length}
                          <small>/ {locations.length} on campus</small>
                        </strong>
                      </div>
                      <span className="stat-extra">Room for your day</span>
                    </div>
                    <div className="stat">
                      <span className="stat-icon peach">
                        <Clock3 size={21} />
                      </span>
                      <div>
                        <span>Average estimated wait</span>
                        <strong>
                          {averageWait ?? "—"}
                          <small>{averageWait !== null && "min"}</small>
                        </strong>
                      </div>
                      <span className="stat-extra">Across open spaces</span>
                    </div>
                    <div className="stat">
                      <span className="stat-icon mint">
                        <Leaf size={21} />
                      </span>
                      <div>
                        <span>Quiet spots right now</span>
                        <strong>
                          {quiet.length}
                          <small>spaces</small>
                        </strong>
                      </div>
                      <button
                        className="stat-link"
                        onClick={() => setOnlyQuiet(!onlyQuiet)}
                      >
                        {onlyQuiet ? "See all" : "Explore"}{" "}
                        <ArrowUpRight size={14} />
                      </button>
                    </div>
                  </div>
                </>
              )}

              <section id="spaces" className="spaces-section">
                <div className="section-heading">
                  <div>
                    <h2>
                      {page === "overview"
                        ? "Around campus"
                        : page === "saved"
                          ? "A few familiar favorites"
                          : page === "forecasts"
                            ? "Look a little ahead"
                            : "Get the lay of the land"}
                      <span>
                        {page === "saved" ? saved.length : locations.length}{" "}
                        spaces
                      </span>
                    </h2>
                    {page === "overview" && (
                      <p>Check the vibe before you head over.</p>
                    )}
                  </div>
                  <span className="updated">
                    <Activity size={13} />
                    Updated {time(data.updated_at, data.timezone)}
                  </span>
                </div>
                <div className="filters">
                  <div
                    className="category-tabs"
                    role="group"
                    aria-label="Filter by category"
                  >
                    {categories.map((item) => (
                      <button
                        className={category === item.id ? "active" : ""}
                        onClick={() => setCategory(item.id)}
                        key={item.id}
                      >
                        <item.icon size={15} />
                        {item.name}
                      </button>
                    ))}
                  </div>
                  <div className="search-sort">
                    <label className="search-box">
                      <Search size={16} />
                      <input
                        aria-label="Search spaces"
                        placeholder="Search a space…"
                        value={query}
                        onChange={(event) => setQuery(event.target.value)}
                      />
                      {query && (
                        <button
                          onClick={() => setQuery("")}
                          aria-label="Clear search"
                        >
                          <X size={13} />
                        </button>
                      )}
                    </label>
                    {page !== "map" && (
                      <label className="sort-box">
                        <select
                          aria-label="Sort spaces"
                          value={sort}
                          onChange={(event) => setSort(event.target.value)}
                        >
                          <option value="recommended">Quietest first</option>
                          <option value="walk">Nearest first</option>
                          <option value="name">Name A–Z</option>
                        </select>
                        <ChevronDown size={14} />
                      </label>
                    )}
                  </div>
                </div>
                {onlyQuiet && (
                  <div className="active-filter">
                    <Leaf size={13} />
                    Quiet spaces only
                    <button
                      onClick={() => setOnlyQuiet(false)}
                      aria-label="Remove quiet spaces filter"
                    >
                      <X size={13} />
                    </button>
                  </div>
                )}
                {page === "map" ? (
                  <CampusMap
                    locations={filtered}
                    onOpen={setSelected}
                    highlighted={highlighted}
                  />
                ) : page === "forecasts" ? (
                  <>
                    <div className="forecast-toolbar">
                      <span>
                        <Clock3 size={16} /> When are you heading over?
                      </span>
                      <div className="horizon-buttons">
                        {[15, 30, 60, 90, 120].map((value) => (
                          <button
                            key={value}
                            className={value === horizon ? "active" : ""}
                            onClick={() => setHorizon(value)}
                          >
                            {value < 60 ? `${value} min` : `${value / 60} hr`}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="forecast-table-wrap">
                      <table className="forecast-table">
                        <thead>
                          <tr>
                            <th>Campus space</th>
                            <th>Right now</th>
                            <th>In {horizon} min</th>
                            <th>Est. wait</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {filtered.map((location) => {
                            const point = location.forecast.find(
                              (value) => value.minutes_ahead === horizon,
                            );
                            return (
                              <tr key={location.id}>
                                <td>
                                  <button
                                    onClick={() => setSelected(location.id)}
                                  >
                                    <span
                                      className={`table-icon ${location.category}`}
                                    >
                                      {location.category === "dining" ? (
                                        <Coffee size={18} />
                                      ) : location.category === "fitness" ? (
                                        <Dumbbell size={18} />
                                      ) : (
                                        <GraduationCap size={18} />
                                      )}
                                    </span>
                                    <span>
                                      <strong>{location.name}</strong>
                                      <small>{location.category}</small>
                                    </span>
                                  </button>
                                </td>
                                <td>
                                  <Badge status={location.status} />
                                </td>
                                <td>
                                  {point ? (
                                    <span
                                      className={`forecast-percent ${point.percent < location.percent ? "decreasing" : ""}`}
                                    >
                                      {point.is_open
                                        ? `${point.percent}% occupied`
                                        : "Closed"}
                                      {point.is_open &&
                                        point.percent <
                                          location.percent - 4 && (
                                          <ArrowDown size={13} />
                                        )}
                                    </span>
                                  ) : (
                                    "Awaiting forecast"
                                  )}
                                </td>
                                <td>
                                  {point?.is_open
                                    ? point.wait_minutes === 0
                                      ? "No wait"
                                      : `${point.wait_minutes} min`
                                    : "—"}
                                </td>
                                <td>
                                  <button
                                    className="icon-button"
                                    aria-label={`View forecast for ${location.name}`}
                                    onClick={() => setSelected(location.id)}
                                  >
                                    <ArrowUpRight size={18} />
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    <div className="model-note">
                      <Sparkles size={18} />
                      <div>
                        <strong>A forecast, with context.</strong>
                        <span>
                          Time of day, weather, campus events, and current
                          occupancy help estimate what’s next.
                          {data.model.source === "synthetic" &&
                            " This demo uses a model trained on simulated data."}
                        </span>
                      </div>
                      <button onClick={() => setShowHelp(true)}>
                        How it works <ArrowUpRight size={14} />
                      </button>
                    </div>
                  </>
                ) : filtered.length > 0 ? (
                  <div className="locations-grid">
                    {filtered.map((location, index) => (
                      <LocationCard
                        key={location.id}
                        location={location}
                        index={index}
                        saved={saved.includes(location.id)}
                        checkedIn={checkin.location_id === location.id}
                        onSave={() => toggleSave(location.id)}
                        onOpen={() => setSelected(location.id)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">
                    <Bookmark size={30} />
                    <h3>
                      {page === "saved" && !saved.length
                        ? "Make yourself at home."
                        : "No spaces found."}
                    </h3>
                    <p>
                      {page === "saved" && !saved.length
                        ? "Save a few favorite spaces with the bookmark button. They’ll be waiting here."
                        : "Try another category or clear your filters."}
                    </p>
                    <button
                      className="secondary-button"
                      onClick={() => {
                        if (page === "saved" && !saved.length)
                          navigate("overview");
                        else {
                          setQuery("");
                          setCategory("all");
                          setOnlyQuiet(false);
                        }
                      }}
                    >
                      {page === "saved" && !saved.length
                        ? "Explore campus"
                        : "Clear filters"}
                      <ArrowRight size={15} />
                    </button>
                  </div>
                )}
              </section>
              {page === "overview" && nextEvent && (
                <div className="event-strip">
                  <span className="event-icon">
                    <CalendarDays size={19} />
                  </span>
                  <div>
                    <span>
                      ON CAMPUS TODAY{data.demo_mode && " · DEMO EVENT"}
                    </span>
                    <strong>
                      {nextEvent.title}
                      <small>
                        {nextEvent.venue} ·{" "}
                        {time(nextEvent.starts_at, data.timezone)}
                      </small>
                    </strong>
                  </div>
                  <span className="event-caption">
                    A little busier nearby. Plan a few minutes ahead.
                  </span>
                </div>
              )}
              <footer className="page-footer">
                <span>
                  <Logo small /> Your campus. A little more in flow.
                </span>
                <button onClick={() => setShowHelp(true)}>
                  {data.demo_mode
                    ? "Demo campus · Simulated occupancy & forecasts"
                    : "Estimates update with campus observations"}
                  <HelpCircle size={12} />
                </button>
              </footer>
            </>
          )}
        </main>
      </div>

      {detail && data && (
        <Modal label={detail.name} wide onClose={() => setSelected(null)}>
          <VenueArt category={detail.category} />
          <div className="detail-content">
            <div className="detail-title">
              <div>
                <span className="eyebrow">
                  {detail.category} · {detail.walk_minutes} MIN WALK
                </span>
                <h2>{detail.name}</h2>
                <p>
                  <MapPin size={14} />
                  {detail.building}
                </p>
              </div>
              <button
                className={`icon-button ${saved.includes(detail.id) ? "is-saved" : ""}`}
                onClick={() => toggleSave(detail.id)}
                aria-label={`${saved.includes(detail.id) ? "Unsave" : "Save"} ${detail.name}`}
              >
                <Bookmark
                  fill={saved.includes(detail.id) ? "currentColor" : "none"}
                  size={21}
                />
              </button>
            </div>
            <p className="detail-description">{detail.description}</p>
            <div className="detail-tags">
              {detail.tags.map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
            <div className="detail-stats">
              <div>
                <Badge status={detail.status} />
                <strong>
                  {detail.stale ? "—" : `${detail.percent}%`}
                  <span>occupied now</span>
                </strong>
              </div>
              <div>
                <Users size={19} />
                <strong>
                  {detail.stale || !detail.is_open ? "—" : detail.available}
                  <span>available spots</span>
                </strong>
              </div>
              <div>
                <Clock3 size={19} />
                <strong>
                  {detail.wait_minutes == null || !detail.is_open
                    ? "—"
                    : `${detail.wait_minutes} min`}
                  <span>estimated wait</span>
                </strong>
              </div>
            </div>
            <div className="detail-chart-heading">
              <h3>Your next two hours</h3>
              <span>
                <i /> Estimated range
              </span>
            </div>
            <ForecastChart location={detail} timezone={data.timezone} />
            {detail.forecast.length > 0 && (
              <div className="best-time">
                <Sparkles size={15} />
                {(() => {
                  const best = [...detail.forecast]
                    .filter((point) => point.is_open)
                    .sort((a, b) => a.percent - b.percent)[0];
                  return best ? (
                    <span>
                      {best.percent < detail.percent - 5 ? (
                        <>
                          Try around{" "}
                          <strong>{time(best.at, data.timezone)}</strong> —
                          about {best.percent}% occupied.
                        </>
                      ) : (
                        <>
                          Now looks like a good time. Crowds are{" "}
                          {detail.status === "busy"
                            ? "expected to stay high"
                            : "fairly steady"}
                          .
                        </>
                      )}
                    </span>
                  ) : (
                    <span>
                      This space closes soon. Check the opening hours below.
                    </span>
                  );
                })()}
              </div>
            )}
            <div className="detail-hours">
              <Clock3 size={14} />
              {detail.opens === 0 && detail.closes === 24
                ? "Open 24 hours"
                : `Open daily · ${hours(detail.opens)}–${hours(detail.closes)}`}
              <button
                onClick={() => {
                  setHighlighted(detail.id);
                  setSelected(null);
                  navigate("map");
                }}
              >
                View on campus map <ArrowUpRight size={14} />
              </button>
            </div>
            <div className="detail-actions">
              <button
                className="primary-button"
                disabled={
                  busy ||
                  !detail.is_open ||
                  (detail.occupancy >= detail.capacity &&
                    checkin.location_id !== detail.id)
                }
                onClick={() =>
                  updateCheckin(
                    checkin.location_id === detail.id ? undefined : detail.id,
                  )
                }
              >
                {busy
                  ? "Updating…"
                  : checkin.location_id === detail.id
                    ? "Check out"
                    : !detail.is_open
                      ? "Currently closed"
                      : detail.occupancy >= detail.capacity
                        ? "At capacity"
                        : "Check in here"}
                <Check size={16} />
              </button>
              <button
                className={`secondary-button ${subscriptions.includes(detail.id) ? "subscribed" : ""}`}
                onClick={() => toggleSubscribe(detail.id)}
              >
                {subscriptions.includes(detail.id) ? (
                  <BellOff size={16} />
                ) : (
                  <Bell size={16} />
                )}{" "}
                {subscriptions.includes(detail.id)
                  ? "Alerts on"
                  : "Crowd alerts"}
              </button>
            </div>
            <p className="detail-disclaimer">
              {data.demo_mode
                ? "Demo occupancy and model predictions use simulated data. "
                : `Occupancy source: ${detail.source}. `}
              Check-ins expire after {data.checkin_expiry_hours} hours. Crowd
              alerts arrive while this app is open.
            </p>
          </div>
        </Modal>
      )}

      {showHelp && (
        <Modal label="About FlowCast" onClose={() => setShowHelp(false)}>
          <div className="help-content">
            <Logo />
            <span className="eyebrow">A LITTLE LESS WAITING</span>
            <h2>
              Life on campus,
              <br />
              with better timing.
            </h2>
            <p>
              FlowCast helps you find a good time to eat, move, and focus. Check
              live occupancy, look ahead, and save your go-to spots.
            </p>
            <div className="help-feature">
              <Activity size={20} />
              <div>
                <strong>Fresh updates, as they happen</strong>
                <p>
                  Counts update automatically. Check in when you arrive and
                  check out when you leave.
                </p>
              </div>
            </div>
            <div className="help-feature">
              <TrendingUp size={20} />
              <div>
                <strong>Forecasts with context</strong>
                <p>
                  Gradient boosting models learn occupancy and wait times from
                  current counts, time, weather, and campus events. The shaded
                  area shows an estimated error range from held-out
                  observations.
                </p>
              </div>
            </div>
            <div className="help-feature">
              <Bell size={20} />
              <div>
                <strong>A heads-up for your favorite spaces</strong>
                <p>
                  Turn on crowd alerts to hear when a space becomes quiet or
                  busy. Keep the app open to receive them.
                </p>
              </div>
            </div>
            {data && (
              <div className="model-details">
                <strong>
                  {data.demo_mode
                    ? "You’re exploring a demo campus"
                    : "Your campus data"}
                </strong>
                <p>
                  {data.model.source === "synthetic"
                    ? "Northwood University, occupancy, weather, events, and training observations are fictional. These forecasts demonstrate the workflow and do not reflect a real campus."
                    : data.model.source === "observed"
                      ? "Forecasts use a model trained on observed campus data. Predictions are estimates, and fresh measurements matter."
                      : "A model trained on real observations is needed before forecasts become available."}
                </p>
                {data.model.training_rows && (
                  <div className="model-metrics">
                    <span>
                      <strong>
                        {data.model.training_rows.toLocaleString()}
                      </strong>
                      training samples
                    </span>
                    <span>
                      <strong>{data.model.occupancy_mae_pp} pp</strong>occupancy
                      error
                    </span>
                    <span>
                      <strong>{data.model.wait_mae_minutes} min</strong>
                      wait-time error
                    </span>
                  </div>
                )}
                <small>
                  Error metrics use a chronological validation split. Demo
                  metrics measure simulated data only.
                </small>
              </div>
            )}
            <button
              className="primary-button"
              onClick={() => setShowHelp(false)}
            >
              Find your flow <ArrowRight size={15} />
            </button>
          </div>
        </Modal>
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
          <button
            onClick={() => setToast("")}
            aria-label="Dismiss notification"
          >
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
