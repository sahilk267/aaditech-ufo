import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type ChartPoint = {
  time: string;
  health: number;
  load: number;
};

type Props = {
  data: ChartPoint[];
};

export function SystemHealthChart({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="time" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="health" stroke="#10b981" name="Health %" strokeWidth={2} />
        <Line type="monotone" dataKey="load" stroke="#f59e0b" name="Load %" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}