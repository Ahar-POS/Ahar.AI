import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    LineChart,
    Line
} from 'recharts';

const topDishesData = [
    { name: 'Pizza Margherita', sold: 160 },
    { name: 'Spaghetti Carbonara', sold: 145 },
    { name: 'Tiramisù', sold: 98 },
    { name: 'Risotto Funghi', sold: 87 },
    { name: 'Bruschetta', sold: 76 }
];

const hourlyData = [
    { time: '11:00', orders: 12 },
    { time: '12:00', orders: 25 },
    { time: '13:00', orders: 42 },
    { time: '14:00', orders: 30 },
    { time: '18:00', orders: 20 },
    { time: '19:00', orders: 55 },
    { time: '20:00', orders: 68 },
    { time: '21:00', orders: 45 },
];

export default function KitchenTab() {
    return (
        <div>
            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="metric-header">
                        <span className="metric-label">Avg Fulfillment</span>
                        <span className="metric-icon">⏱️</span>
                    </div>
                    <div className="metric-value">14 min</div>
                    <div className="metric-subtext">Per order target: 15m</div>
                </div>
                <div className="metric-card">
                    <div className="metric-header">
                        <span className="metric-label">Orders Completed</span>
                        <span className="metric-icon">✅</span>
                    </div>
                    <div className="metric-value">847</div>
                    <div className="metric-subtext text-success">↑ 12% vs yesterday</div>
                </div>
                <div className="metric-card">
                    <div className="metric-header">
                        <span className="metric-label">Peak Time</span>
                        <span className="metric-icon">📈</span>
                    </div>
                    <div className="metric-value">20:00</div>
                    <div className="metric-subtext">68 orders/hour</div>
                </div>
            </div>

            <div className="charts-grid mt-4">
                <div className="chart-card">
                    <h4 className="chart-title mb-2">Top Performing Dishes</h4>
                    <ResponsiveContainer width="100%" height={280}>
                        <BarChart data={topDishesData} margin={{ top: 20, right: 30, left: 0, bottom: 30 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#6b7280' }} angle={-45} textAnchor="end" height={90} interval={0} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                            <Tooltip cursor={{ fill: '#f3f4f6' }} contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }} />
                            <Bar dataKey="sold" fill="#ef4444" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                <div className="chart-card">
                    <h4 className="chart-title mb-2">Total Orders by Hour</h4>
                    <ResponsiveContainer width="100%" height={250}>
                        <LineChart data={hourlyData} margin={{ top: 20, right: 30, left: 0, bottom: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                            <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} dy={10} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                            <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }} />
                            <Line type="monotone" dataKey="orders" stroke="#ef4444" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
}
