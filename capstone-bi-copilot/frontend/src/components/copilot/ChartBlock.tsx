import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartSpec } from "../../types/contracts";

interface ChartBlockProps {
  spec: ChartSpec;
}

const SERIES_COLORS = ["#7657a7", "#ac78aa", "#6b94a8", "#c58d7e", "#7184aa"];

export function ChartBlock({ spec }: ChartBlockProps) {
  if (spec.type === "none" || spec.rows.length === 0) return null;
  if (spec.type === "table") return <ChartTable spec={spec} />;

  const xKey = spec.x_key ?? Object.keys(spec.rows[0] ?? {})[0];
  const yKeys = spec.y_keys.length ? spec.y_keys : Object.keys(spec.rows[0] ?? {}).filter((key) => key !== xKey);
  const common = (
    <>
      <CartesianGrid stroke="rgba(23, 20, 29, .08)" vertical={false} />
      <XAxis dataKey={xKey} tick={{ fontSize: 12 }} stroke="rgba(23, 20, 29, .42)" />
      <YAxis tick={{ fontSize: 12 }} stroke="rgba(23, 20, 29, .42)" width={42} />
      <Tooltip contentStyle={{ border: 0, borderRadius: 10, boxShadow: "0 8px 28px rgba(55, 48, 72, .12)" }} />
      {yKeys.length > 1 && <Legend />}
    </>
  );

  return (
    <figure className="chart-block" aria-label={spec.title || "Response chart"}>
      {spec.title && <figcaption>{spec.title}</figcaption>}
      <div className="chart-canvas">
        <ResponsiveContainer width="100%" height="100%">
          {spec.type === "bar" ? (
            <BarChart data={spec.rows}>{common}{yKeys.map((key, index) => <Bar key={key} dataKey={key} fill={SERIES_COLORS[index % SERIES_COLORS.length]} radius={[4, 4, 0, 0]} />)}</BarChart>
          ) : spec.type === "area" ? (
            <AreaChart data={spec.rows}>{common}{yKeys.map((key, index) => <Area key={key} type="monotone" dataKey={key} stroke={SERIES_COLORS[index % SERIES_COLORS.length]} fill={SERIES_COLORS[index % SERIES_COLORS.length]} fillOpacity={0.14} />)}</AreaChart>
          ) : spec.type === "pie" ? (
            <PieChart><Tooltip /><Pie data={spec.rows} dataKey={yKeys[0]} nameKey={xKey} innerRadius="48%" outerRadius="76%" paddingAngle={2}>{spec.rows.map((_, index) => <Cell key={index} fill={SERIES_COLORS[index % SERIES_COLORS.length]} />)}</Pie></PieChart>
          ) : (
            <LineChart data={spec.rows}>{common}{yKeys.map((key, index) => <Line key={key} type="monotone" dataKey={key} stroke={SERIES_COLORS[index % SERIES_COLORS.length]} strokeWidth={2} dot={false} />)}</LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

function ChartTable({ spec }: ChartBlockProps) {
  const columns = Object.keys(spec.rows[0] ?? {});
  return (
    <figure className="chart-block">
      {spec.title && <figcaption>{spec.title}</figcaption>}
      <div className="table-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{spec.rows.map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{String(row[column] ?? "")}</td>)}</tr>)}</tbody></table></div>
    </figure>
  );
}
