import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer
} from 'recharts';

const sentimentData = [
    { day: 'Mon', rating: 4.2 },
    { day: 'Tue', rating: 4.5 },
    { day: 'Wed', rating: 4.6 },
    { day: 'Thu', rating: 4.8 },
    { day: 'Fri', rating: 4.9 },
    { day: 'Sat', rating: 4.9 },
    { day: 'Sun', rating: 4.7 },
];

export default function CustomerTab() {
    return (
        <div>
            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="metric-header">
                        <span className="metric-label">Avg Rating</span>
                        <span className="metric-icon">⭐️</span>
                    </div>
                    <div className="metric-value">4.8 <span className="text-muted text-sm">/ 5.0</span></div>
                    <div className="metric-subtext text-success">↑ +0.2 vs last month</div>
                </div>
                <div className="metric-card">
                    <div className="metric-header">
                        <span className="metric-label">Wait Time Sentiment</span>
                        <span className="metric-icon">⏳</span>
                    </div>
                    <div className="metric-value text-success">Positive</div>
                    <div className="metric-subtext">Based on 42 reviews</div>
                </div>
                <div className="metric-card">
                    <div className="metric-header">
                        <span className="metric-label">Returning Guests</span>
                        <span className="metric-icon">👋</span>
                    </div>
                    <div className="metric-value">34%</div>
                    <div className="metric-subtext text-success">↑ +2% vs last week</div>
                </div>
            </div>

            <div className="charts-grid mt-4">
                <div className="chart-card" style={{ gridColumn: 'span 2' }}>
                    <h4 className="chart-title mb-2">Customer Satisfaction Trend (7 Days)</h4>
                    <ResponsiveContainer width="100%" height={260}>
                        <AreaChart data={sentimentData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                            <defs>
                                <linearGradient id="colorRating" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e5e7eb" />
                            <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                            <YAxis domain={[3.5, 5]} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6b7280' }} />
                            <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }} />
                            <Area type="monotone" dataKey="rating" stroke="#10b981" fillOpacity={1} fill="url(#colorRating)" strokeWidth={3} />
                        </AreaChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
}
